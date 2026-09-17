# RAG 企业级改造优先级清单

> 版本:v1(2026-09-09)
> 方案定位:把 rag-service 做成**统一检索基础设施(存储+切分+向量化+粗召回,namespace 隔离)**,
> ai-service 保留**编排面(工具调用/精排/拼装/回答/热调/评测)**——数据面统一、控制面解耦。
> 目标:按"成本收益比"给 8 个设计维度排改造优先级,每项给出责任模块/接口/验收指标。
> 状态:**规划中,未动代码**。

---

## 0. 总览(优先级梯队)

| 梯队 | 维度 | 优先级 | 一句话理由 | 状态 |
| --- | --- | --- | --- | --- |
| P0 | 数据面收敛(统一存储+检索到 rag-service) | 高 | 否则"跨来源检索"是空谈 | 规划 |
| P0 | 可用性降级(L1 兜底) | 高 | 抽离后必须保系统不挂 | 规划 |
| P0 | 索引与召回(混合检索) | 高 | 企业场景术语精确匹配的硬伤 | 规划 |
| P1 | 异步流水线(ingest 解耦) | 中高 | 上传不卡主链路 | 规划 |
| P1 | 安全与合规(权限到 chunk) | 中高 | 多租户数据安全的底线 | 规划 |
| P2 | 检索后处理(粗排/精排分工) | 中 | 精排归编排侧,边界清晰 | 规划 |
| P2 | 版本治理(快照/血缘/重切) | 中 | 文档演进可追溯 | 规划 |
| P3 | 可观测/评测(迁至基础设施) | 中低 | 现 ai-service 已齐,迁移顺带 | 规划 |
| P3 | 数据形态(半结构化/图谱) | 低 | 收益远、成本高,延后 | 后置 |

> **建议推进顺序**(性价比优先):P0 两项 → P1 两项 → P2 → P3 顺带。

---

## 1. P0 · 数据面收敛(统一存储+检索到 rag-service)

### 目标
把 `doc`(用户/知识库文档)与 `mem`(长期记忆)从"ai-service 内建 MySQL JSON 向量"统一
收口到 rag-service 的**同一套 pgvector 存储 + 同一套检索原语**,用 namespace 隔离知识域。

### 责任模块
- **rag-service**:文档/chunk 入库、向量化、检索原语(见 §接口)。
- **ai-service**:`search_docs` 工具改为 HTTP 调 rag-service `/search`(工具/编排不动)。

### 接口契约
```
# 入库(异步向量化,上传即返回)
POST /api/rag/ingest
  { namespace: "doc|mem" | kbId, doc_id, texts, source, user_id }
  → 200 { ingest_id }

# 检索(Agent 与记忆召回共用)
POST /api/rag/search
  { namespace, query, top_k?, threshold? }
  → { hits: [{chunk_id, score, snippet, source}], latency_ms }

# 删除(按 namespace 隔离)
DELETE /api/rag/{namespace}/{doc_id}
```

### 验收指标
- 前端上传→入库走 rag-service,ai-service 不再写 `documents/chunks`。
- `search_docs` 返回片段来源均为 rag-service,带 `namespace` 与 `score`。
- 向量存储从 MySQL JSON 字符串迁移至 pgvector(触发一次数据搬迁,见 §4)。

---

## 2. P0 · 索引与召回(混合检索)

### 目标
在 rag-service 检索原语中加入 **BM25 关键词召回 + 向量召回**并集,再粗排。
解决当前 [search_chunks](file:///D:/selfFile/python/vue3/v3agent/packages/ai-service/app/rag/engine.py)
纯向量线性扫描对"合同号/人名/专有名词"失效的问题。

### 责任模块
- **rag-service**:增加 BM25 索引(如 pg full-text / lucene 类组件),检索原语二路召回合并。
- **ai-service**:不改,消费统一 `/search` 结果即可。

### 接口变化
- `/search` `mode: "hybrid"|"vector"|"keyword"`,默认 hybrid。

### 验收指标
- 对含术语的评测 query,`recall@k` 相对纯向量提升(目标 +15% 以上)。
- `mode=keyword` 能命中纯关键词精确匹配。

---

## 3. P1 · 异步流水线(ingest 解耦)

### 目标
上传即返回,切块/向量化/建索引后台异步执行,避免上传卡主链路。

### 责任模块
- **rag-service**:`/ingest` 入队(消息队列/异步任务),状态字段 `pending|processing|ready|failed`,进度可查。

### 接口变化
```
POST /api/rag/ingest        → 立即 202 { ingest_id }
GET  /api/rag/ingest/{id}   → { status, finished, error? }
```

### 验收指标
- 上传接口 P95 不随文档大小显著增长(异步后与向量化耗时解耦)。
- 失败任务有重试与可查状态。

---

## 4. P1 · 安全与合规(权限到 chunk)

### 目标
权限从"namespace 级"下沉到 **chunk 级**(经 namespace + user/知识库过滤检索),支持审计丝带。

### 责任模块
- **rag-service**:检索时按当前身份过滤,返回 meta 携带来源/权限信息。
- **ai-service / 知识库管理端**:透传身份到 `/search`。

### 验收指标
- 未授权的用户检索不到其命名空间外的 chunk。
- 删除文档时相关 chunk 一并清理,无孤儿数据。

---

## 5. P2 · 检索后处理(粗排/精排分工)

### 目标
**粗排 topN 在 rag-service**,精排/重排(LLM 或 cross-encoder)+ 阈值决策归编排侧 ai-service,
避免 rag-service 被"谁用、用什么模型重排"的编排语义污染成"上帝服务"。

### 责任模块
- **rag-service**:`/search` 返回略大的粗集(topN,不含精排)。
- **ai-service**:`search_docs` 拿粗集后做精排、阈值过滤、拼 prompt。

### 验收指标
- rag-service 无任何 LLM 重排依赖,可被任意消费方复用。
- 精排结果与粗集一致,无信息丢失。

---

## 6. P2 · 版本治理(快照/血缘/重切)

### 目标
文档快照、血缘(来源→chunk),支持增量重切与回滚。

### 责任模块
- **rag-service**:文档版本字段、chunk 血缘记录、`/rebuild`(策略变更后重切)。

### 接口变化
- 复用现有 `/rebuild`:仅重切受影响文档,保留历史版本。

### 验收指标
- 修改检索策略后 `rebuild` 只重切该 namespace,不重建全量。
- 可查询某 chunk 来自哪个文档/版本。

---

## 7. P3 · 可观测/评测(迁至基础设施)

### 目标
现 contexteng 的检索事件/recall@k/eval-cases **已齐全**,本次迁移是"顺带":**当检索原语移入
rag-service 后,事件上报与评测指标也应在基础设施侧聚合**,统一跨来源口径。

### 责任模块
- **rag-service**:检索事件流水(复用 cx 语义但独立于 ai-service 实现)。
- **ai-service**:保留编排侧评测,消费基础设施指标。

### 验收指标
- 跨 doc/mem 来源的检索质量指标(DAG 口径)在单一处可查。
- 与现有 contexteng 指标不冲突、不重复埋点。

---

## 8. P3 · 数据形态(半结构化/图谱)【后置】

### 目标
企业文档以表格/半结构化为主,图谱用于实体关联检索。收益远、成本高,明确延后。

### 责任模块
- 未定,仅记录方向(不排进近期计划)。

### 触发条件
- 出现明确的结构化/知识图谱检索需求场景后再评估。

---

## 9. 可用性 · 降级(L1 必须,与 P0 数据面收敛同步落地)

> RAG 定位为**增强项而非必需品**:挂了→优雅降级,不是架第二套 RAG。

### 三级降级策略

| 级别 | RAG 挂了怎么办 | Agent 行为 | 成本 |
| --- | --- | --- | --- |
| **L1 降级为无RAG回答** | `search_docs` 调 rag 失败 → 返回「检索暂不可用,基于自身知识回答」 | 模型照常答,只是无检索片段 | **0(默认必须)** |
| **L2 本地只读快照** | 从 ai-service 本地只读快照索引(上次同步 chunks 子集)检索 | 仍能"查档" | 中(可选) |
| **L3 熔断/冷却** | 网关门控:连续失败后**自动禁用 search_docs 数秒** | 本轮不发检索请求 | 低(可选) |

### 落地要点
- 复用现有「错误即文本」哲学([base.py:35](file:///D:/selfFile/python/vue3/v3agent/packages/ai-service/app/tools/base.py#L35-L37) 同款 try/except)。
- `search_docs` 包一层 wrapper:rag 调不通 → 返回可答性话术,不报错、不卡死、不 500。
- 系统提示词保留「若文档检索不可用,基于已知信息作答」([rag.py:51](file:///D:/selfFile/python/vue3/v3agent/packages/ai-service/app/tools/rag.py#L50-L51) 已有话术)。

### 验收指标
- **stop rag-service 后,Agent 请求仍正常返回**(只是无检索片段),不 500、不超时挂起。

---

## 10. 接口插槽 · 自建 vs 第三方知识库选型

> 现设计天然是**插槽式**:`search_docs` 只认 HTTP `/search` + namespace,不认内部实现。
> 换第三方 = 换一个实现,Agent 侧零改动。

### 塞是三层能力,第三方通常只替其中一层

| 能力 | 第三方能否接 | 该由谁做 |
| --- | --- | --- |
| ① 托管/管理(知识库 CRUD、归属、权限、配额) | 大多能(Dify/RAGFlow 强) | 第三方或自建 |
| ② 摄取+存储+向量化检索(切块/embed/pgvector) | **最常换这里**(Qdrant/Milvus/Pinecone 专精) | **第三方更省维护** |
| ③ Agent 编排+精排+评测(`search_docs`、热调、recall@k) | 不该换 | **必须留 ai-service** |

### 三条选型路径

| 路径 | 做法 | 评价 |
| --- | --- | --- |
| **只换②** | 接 Qdrant/Milvus 做向量存储后端,保留自建外壳接收统一 `/search` | 改动最小,兼得维护省 + 你的编排资产 |
| **整体换①+②** | 直接用 Dify/RAGFlow 当知识库,`search_docs` 指向它 | 最省力,但 contexteng 评测/namespace 需映射到厂商模型 |
| **全自建** | 自建 rag-service 补全 | 仅需深度定制 RAG 算法且人手充足才值 |

### 关键判断
> 用一句话决策:要「**稳定的企业知识库能力**」(→换成熟第三方更划算)vs「**自己完全掌控的 RAG 实验室**」(→ 继续自建)。两条路终点不同。

---

## 11. 交接与风险(落地前必读)

1. **迁移窗口**:数据从 MySQL `chunks` 迁到 pgvector 需一次性脚本,且新旧写路径并存(双写或迁移后切流量)。
2. **部署顺序**:先 rag-service 独立可跑 → 再切 ai-service `search_docs` 指向它 → 后停 ai-service 内建写路径。
3. **namespace 语法**:定调 `doc:{kbId}` / `mem:{userId}` 复合串,还是扁平 `doc|mem` + 字段,影响权限模型粒度——**落地前先敲定**(见对话记录遗留决策点)。
4. **context 观测数据(cx_*)不进基础设施**:它是元数据/日志,不是知识内容,留在 ai-service(避免辛普悖论)。
5. **重排边界**:精排必须留在编排侧,否则 rag-service 被编排语义污染。

---