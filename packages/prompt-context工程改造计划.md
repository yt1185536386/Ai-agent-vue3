# Prompt 工程 + Context 工程 改造计划

> 版本:v1(2026-08-27)
> 方案定位:**逻辑独立、部署合一**——两模块作为 `ai-service/app/` 下的业务子模块实现,
> harness 只留裸钩子;表结构、事件模型、API 契约按"将来可整体拆为独立服务"的标准设计。
> 目标:以召回精度/准确率等指标驱动文本切分、相似度方法、Prompt 模板的持续调优。

---

## 1. 总体结构

```
ai-service/app/
├── harness/                 # 引擎层:只加 3 个裸钩子(见 §3),不 import 业务模块
│   ├── prompts.py           # 扩展:模板加载注入点 + 装配完成钩子
│   └── loop.py              # 扩展:context 快照钩子
│
├── prompteng/               # 【新增】Prompt 工程模块(内容生产者)
│   ├── __init__.py
│   ├── models.py            # pe_* 表(模板/版本/使用事件/日聚合)
│   ├── service.py           # 模板 CRUD、版本激活、渲染(被 harness 钩子回调)
│   ├── metrics.py           # prompt 维度指标聚合查询
│   └── api.py               # /v1/pe/* 路由
│
├── contexteng/              # 【新增】Context 工程模块(现场记录者)
│   ├── __init__.py
│   ├── models.py            # cx_* 表(检索事件/context 快照/评测用例/日聚合)
│   ├── events.py            # 事件模型定义(两模块共用的契约)
│   ├── collector.py         # 钩子实现:异步落库、失败静默
│   ├── metrics.py           # context 维度指标聚合查询
│   └── api.py               # /v1/cx/* 路由
│
├── rag.py                   # 被调优对象:切分/相似度参数化(见 §6)
├── tools/rag.py             # search_docs:检索事件上报点
├── agent.py                 # 装配:启动时把 collector/service 注入 harness 钩子
└── main.py                  # 挂载 prompteng / contexteng 路由
```

### 分工原则(一句话版)

| 模块              | 负责                                                                           | 不负责                                    |
| ----------------- | ------------------------------------------------------------------------------ | ----------------------------------------- |
| **harness**       | 拼装现场(loop、prompt 装配),发出"发生了什么"的钩子回调                         | 不认识任何 pe*\*/cx*\* 表,不做持久化      |
| **prompteng**     | Prompt 的**内容与生命周期**:模板、版本、激活、渲染、prompt 维度指标            | 不关心 context 里其他部分(历史/工具/检索) |
| **contexteng**    | Context 的**观测与记录**:检索事件、context 快照、召回/利用率指标、评测用例回收 | 不改变 context 内容(第一阶段只观测不干预) |
| **eval 包**(已有) | 离线指标的生产者:Recall@K / Precision@K / 回归通过率                           | 不动,报告由 contexteng 收纳入库           |

> 第一阶段 contexteng **只观测不干预**:token 预算、裁剪、历史压缩等"干预型"能力
> 等观测数据积累后作为第二阶段加入(接口预留,见 §10)。

---

## 2. 建表统一规范

### 2.1 命名规则

现有表为裸名(`conversations`/`messages`/`documents`/`chunks`)。为避免与存量及
NestJS 侧表混淆,新表统一规则:

```
<域前缀>_<实体名>[_<用途后缀>]

域前缀:  pe_  = Prompt Engineering(Prompt 工程模块)
         cx_  = Context Engineering(Context 工程模块)
实体名:  单数、蛇形,如 template / retrieval_event
用途后缀: _versions(子表)  _daily(日聚合)  _events(事件流水)
```

**规则说明:**

- 两模块表零外键跨域——pe*\* 不引用 cx*\_,cx\_\_ 不引用 documents/chunks
  (chunk_id 只作逻辑记录,不建 FK),这是将来拆库拆服务的前提;
- 所有表必须带 `__table_args__ = {"comment": ...}` 表注释;
- 所有列必须带 `comment=`,说明语义、单位、枚举取值;
- 公共列统一:`id`(String(64),uuid hex 主键)、`created_at`(DateTime,默认 utcnow,
  注释"UTC 入库时间")、可选 `user_id`(String(64),index,注释"NestJS 用户 ID,逻辑关联不建 FK")。

### 2.2 pe\_\* 表(Prompt 工程)

**`pe_templates` — Prompt 模板主表**

| 列                      | 类型                    | comment                                                    |
| ----------------------- | ----------------------- | ---------------------------------------------------------- |
| id                      | String(64) PK           | 模板 ID(uuid hex)                                          |
| key                     | String(64) unique index | 模板标识,代码中引用用,如 'agent.system'、'rag.search_docs' |
| name                    | String(100)             | 展示名,如「Agent 系统提示词」                              |
| group                   | String(32) index        | 模板分组:system / tool / judge / other                     |
| description             | String(500)             | 模板用途、影响面说明                                       |
| status                  | String(16)              | 状态:active / disabled(disabled 时回退代码内默认)          |
| current_version         | int                     | 当前激活版本号,冗余便于查询                                |
| created_at / updated_at | DateTime                | 创建 / 最近修改时间(UTC)                                   |

**`pe_template_versions` — 模板版本表(每次修改产生新版本,不原地改)**

| 列          | 类型                          | comment                                                              |
| ----------- | ----------------------------- | -------------------------------------------------------------------- |
| id          | String(64) PK                 | 版本记录 ID                                                          |
| template_id | String(64) FK→pe_templates.id | 所属模板(域内唯一 FK)                                                |
| version     | int                           | 版本号,模板内单调递增,与 template_id 联合唯一                        |
| content     | Text                          | 模板文本,变量用 {{var}} 占位                                         |
| variables   | Text                          | 变量说明 JSON:[{"name":"rules","desc":"业务规则块","required":true}] |
| status      | String(16)                    | draft / active / archived;同一模板同一时刻仅一个 active              |
| note        | String(500)                   | 版本变更说明(改了什么、为什么)                                       |
| created_at  | DateTime                      | UTC 创建时间                                                         |

**`pe_usage_events` — Prompt 使用事件流水(每次模型调用一条)**

| 列              | 类型             | comment                                                         |
| --------------- | ---------------- | --------------------------------------------------------------- |
| id              | String(64) PK    | 事件 ID                                                         |
| template_key    | String(64) index | 对应 pe_templates.key,逻辑关联                                  |
| version         | int              | 本次实际使用的版本号(监控按版本归因的关键)                      |
| conversation_id | String(64) index | 会话 ID,逻辑关联 conversations.id                               |
| user_id         | String(64) index | 用户 ID                                                         |
| prompt_tokens   | int              | 本次 prompt 部分 token 数;取自模型返回 usage,缺失时 -1 表示未知 |
| latency_ms      | int              | 模型调用耗时(毫秒)                                              |
| created_at      | DateTime         | UTC 事件时间                                                    |

**`pe_metrics_daily` — Prompt 指标日聚合(定时任务或查询时惰性聚合)**

| 列                | 类型             | comment                                         |
| ----------------- | ---------------- | ----------------------------------------------- |
| id                | String(64) PK    | 记录 ID                                         |
| stat_date         | String(10) index | 统计日,格式 YYYY-MM-DD(本地时区)                |
| template_key      | String(64) index | 模板标识                                        |
| version           | int              | 版本号;0 表示「全部版本合计」行                 |
| call_count        | int              | 当日调用次数                                    |
| avg_prompt_tokens | float            | 平均 prompt token(剔除 -1 未知值)               |
| avg_latency_ms    | float            | 平均耗时(毫秒)                                  |
| eval_pass_rate    | float            | 当日最近一次回归评测通过率(0-1);未跑评测为 NULL |

### 2.3 cx\_\* 表(Context 工程)

**`cx_retrieval_events` — 检索事件流水(search_docs 每次调用一条)**

| 列              | 类型             | comment                                                             |
| --------------- | ---------------- | ------------------------------------------------------------------- |
| id              | String(64) PK    | 事件 ID                                                             |
| user_id         | String(64) index | 用户 ID                                                             |
| conversation_id | String(64) index | 会话 ID                                                             |
| query           | Text             | 检索 query(模型自主生成的检索词,非用户原文)                         |
| strategy        | String(64)       | 检索策略标识,如 'chunk600_ov80_cosine',调参实验分组用               |
| top_k           | int              | 请求的 top_k                                                        |
| threshold       | float            | 相似度阈值                                                          |
| hits            | Text             | 命中明细 JSON:[{"chunk_id","doc_id","score","position"}],按分数降序 |
| hit_count       | int              | 过阈值后的命中数;0 即零结果事件                                     |
| max_score       | float            | 最高相似度;零结果时为候选最高分(便于分析阈值合理性)                 |
| latency_ms      | int              | 检索耗时(含 embedding,毫秒)                                         |
| created_at      | DateTime index   | UTC 事件时间                                                        |

**`cx_context_snapshots` — Context 快照(每次模型决策调用一条,context 监控的核心)**

| 列              | 类型             | comment                                                 |
| --------------- | ---------------- | ------------------------------------------------------- |
| id              | String(64) PK    | 快照 ID                                                 |
| conversation_id | String(64) index | 会话 ID                                                 |
| user_id         | String(64) index | 用户 ID                                                 |
| model           | String(64)       | 本次调用的模型名                                        |
| total_tokens    | int              | 本次发送的总 prompt token(取 usage;未知 -1)             |
| system_tokens   | int              | 系统提示词部分 token(估算,见 §3 注)                     |
| history_tokens  | int              | 对话历史部分 token(估算)                                |
| tool_tokens     | int              | 工具结果消息部分 token(估算)                            |
| message_count   | int              | 发送的消息总条数(含 system)                             |
| rag_chunk_ids   | Text             | 本会话最近检索注入的 chunk_id 列表 JSON;无注入为 '[]'   |
| rag_injected    | int              | 本轮 context 是否含检索内容:1 是 0 否                   |
| truncated       | int              | 是否发生裁剪:1 是 0 否;第一阶段恒 0(干预能力上线前预留) |
| created_at      | DateTime index   | UTC 快照时间                                            |

> 注:精确分词依赖 tokenizer,第一阶段 system/history/tool 三部分用
> `len(text) / 1.6`(中英混合经验系数)估算并在 comment 中注明"估算值";
> total_tokens 以模型 usage 为准。第二阶段接入真实 tokenizer 后回填修正。

**`cx_eval_cases` — 检索评测用例(ground truth,支持线上回收)**

| 列              | 类型          | comment                                                        |
| --------------- | ------------- | -------------------------------------------------------------- |
| id              | String(64) PK | 用例 ID                                                        |
| query           | Text          | 评测问题                                                       |
| expect_doc_ids  | Text          | 应命中的文档 ID 列表 JSON(逻辑关联 documents.id)               |
| expect_contains | Text          | 命中 chunk 应包含的关键短语列表 JSON(内容级断言)               |
| source          | String(16)    | 用例来源:manual(人工标注)/ online(线上零结果或低分 query 回收) |
| status          | String(16)    | enabled / disabled                                             |
| created_at      | DateTime      | UTC 创建时间                                                   |

**`cx_metrics_daily` — Context 指标日聚合**

| 列                 | 类型             | comment                                      |
| ------------------ | ---------------- | -------------------------------------------- |
| id                 | String(64) PK    | 记录 ID                                      |
| stat_date          | String(10) index | 统计日 YYYY-MM-DD                            |
| retrieval_count    | int              | 当日检索调用次数                             |
| zero_result_rate   | float            | 零结果率 = 零结果事件数 / 检索总数(0-1)      |
| avg_max_score      | float            | 平均最高相似度(0-1)                          |
| avg_hit_count      | float            | 平均命中 chunk 数                            |
| rag_inject_rate    | float            | 含检索注入的 context 占比(0-1)               |
| avg_context_tokens | float            | 平均 context 总 token                        |
| p95_context_tokens | int              | context token 的 p95                         |
| recall_at_k        | float            | 当日最近一次离线评测 Recall@K;未跑为 NULL    |
| precision_at_k     | float            | 当日最近一次离线评测 Precision@K;未跑为 NULL |

---

## 3. harness 改造点(仅 3 处裸钩子)

原则:harness 新增的都是**可选回调,默认 no-op**,不 import 任何 app 业务模块;
装配代码(agent.py)在启动时注入实现。

### 3.1 `harness/prompts.py` — 模板加载注入点 + 装配钩子

```python
# 新增两个全局可选注入点(默认 None = 维持现状)
_TEMPLATE_LOADER = None   # 签名: (key: str) -> str | None,返回 None 用代码默认
_PROMPT_OBSERVER = None   # 签名: (event: dict) -> None,装配完成后回调

def set_template_loader(fn): ...   # agent.py 启动时注入 prompteng.service.load_content
def set_prompt_observer(fn): ...   # agent.py 启动时注入 collector 回调

def agent_system_prompt() -> str:
    parts = [_now_text()]
    parts.extend(_RULE_BLOCKS.values())
    content = "\n\n".join(parts)
    if _PROMPT_OBSERVER:
        try:
            _PROMPT_OBSERVER({"template_key": "agent.system", "content_len": len(content), ...})
        except Exception:
            pass   # 观测失败绝不影响主链路
    return content
```

`register_rules()` 保持不变;DB 模板激活时由 prompteng 调它完成热更新
(第一阶段不拆 register_rules 机制,改动最小)。

### 3.2 `harness/loop.py` — context 快照钩子

`agent_node` 内、模型调用前后各一个回调点:

```python
_CONTEXT_OBSERVER = None  # 签名: (snapshot: dict) -> None
def set_context_observer(fn): ...

async def agent_node(state):
    msgs = [SystemMessage(content=agent_system_prompt()), *state["messages"]]
    resp = await chat_with_tools.ainvoke(msgs)
    if _CONTEXT_OBSERVER:
        try:
            _CONTEXT_OBSERVER(_build_snapshot(msgs, resp))  # 消息构成 + usage
        except Exception:
            pass
    return {"messages": [resp]}
```

`_build_snapshot` 从 `resp.usage_metadata` 取精确 total/prompt tokens,
按消息 role 归类估算各部分占比(估算规则见 §2.3 注)。

### 3.3 `app/tools/rag.py` — 检索事件上报(非 harness,业务侧)

`search_docs` 内在 `search_chunks` 返回后、阈值过滤后,调用
`contexteng.collector.report_retrieval(...)`(同样 try/except 静默)。
此处同时把硬编码的 `top_k=3`、`score>0.3` 改为从策略配置读取(见 §6)。

**钩子纪律(写入代码注释):** 所有回调必须满足 ① try/except 全捕获;
② 落库用独立 session,不与请求 session 混用;③ 耗时超过 5ms 的部分放后台任务。

---

## 4. API 契约

均由 ai-service 直接暴露;ServerManegeUI 经新增 vite 代理访问。
鉴权沿用 `X-User-Id`/`X-Service-Key` 头部约定,权限校验在 NestJS 侧加权限码(§7.3)。

### Prompt 工程 `/v1/pe/*`

| 方法 | 路径                              | 说明                                           |
| ---- | --------------------------------- | ---------------------------------------------- |
| GET  | `/v1/pe/templates`                | 模板列表(可按 group 过滤)                      |
| POST | `/v1/pe/templates`                | 新建模板(自动建 v1 draft)                      |
| GET  | `/v1/pe/templates/{key}/versions` | 版本列表                                       |
| POST | `/v1/pe/templates/{key}/versions` | 提交新版本(draft)                              |
| POST | `/v1/pe/templates/{key}/activate` | 激活指定版本(热更新 register_rules,记录 note)  |
| POST | `/v1/pe/templates/{key}/disable`  | 停用,回退代码默认                              |
| GET  | `/v1/pe/metrics/overview`         | 看板聚合:各模板调用量、版本分布、token、通过率 |
| GET  | `/v1/pe/metrics/templates/{key}`  | 单模板趋势(按天 × 按版本)                      |

### Context 工程 `/v1/cx/*`

| 方法     | 路径                           | 说明                                                        |
| -------- | ------------------------------ | ----------------------------------------------------------- |
| GET      | `/v1/cx/retrieval/events`      | 检索事件分页查询(时间/用户/零结果过滤)                      |
| GET      | `/v1/cx/retrieval/events/{id}` | 事件详情(命中 chunk 展开)                                   |
| GET      | `/v1/cx/snapshots`             | context 快照分页查询                                        |
| GET      | `/v1/cx/metrics/overview`      | 看板聚合:命中率、分数分布、token 分布                       |
| GET      | `/v1/cx/metrics/trends`        | 趋势序列(按天,含 recall/precision)                          |
| GET/POST | `/v1/cx/eval-cases`            | 评测用例列表 / 新增(含「从零结果事件回收」快捷入口)         |
| POST     | `/v1/cx/eval/run`              | 触发离线 retrieval 评测(调 eval 包,结果写 cx_metrics_daily) |

---

## 5. 监控指标体系(主流设计参照)

参照 Langfuse(观测维度)、RAGAS(RAG 指标)、LangSmith(版本归因)的通行做法,
按「线上实时指标 / 离线评测指标」两层组织——**离线指标才是精度/召回的权威来源,
线上指标用于发现分布漂移**。

### 5.1 Prompt 工程监控

| 指标                    | 类型 | 来源                             | 说明                                             |
| ----------------------- | ---- | -------------------------------- | ------------------------------------------------ |
| 调用量与版本分布        | 线上 | pe_usage_events                  | 每个模板各版本每日调用次数,验证激活/灰度是否生效 |
| Prompt token 均值与趋势 | 线上 | pe_usage_events.prompt_tokens    | 模板改长/改短的直接量化,控制成本与窗口占用       |
| 调用耗时                | 线上 | latency_ms                       | 模板变更对延迟的影响                             |
| 回归评测通过率          | 离线 | eval regression 套件,按版本归因  | 改模板后跑一遍,pass_rate 下跌即退化              |
| 回答质量分(judge)       | 离线 | eval quality 套件均分,按版本归因 | 两版本对比的直接依据                             |
| 沉默模板数              | 线上 | 近 7 天零调用的 active 模板      | 清理与审计线索                                   |

### 5.2 Context 工程监控

| 指标                       | 类型     | 来源                                   | 说明                                              |
| -------------------------- | -------- | -------------------------------------- | ------------------------------------------------- |
| **Recall@K / Precision@K** | **离线** | eval retrieval 套件 + cx_eval_cases    | **核心指标**,切分/相似度调优的裁判                |
| 零结果率                   | 线上     | cx_retrieval_events.hit_count=0 占比   | 检索覆盖不足的直接信号;事件可一键回收为评测用例   |
| 最高相似度分布             | 线上     | max_score 直方图                       | 判断阈值 0.3 是否合理、embedding 区分度           |
| RAG 注入率                 | 线上     | cx_context_snapshots.rag_injected      | 检索内容真正进入 context 的比例(模型调没调用工具) |
| Context token 分布         | 线上     | snapshots total_tokens 均值/p95/直方图 | 窗口占用水位,为后续预算/裁剪策略提供依据          |
| Context 组成占比           | 线上     | system/history/tool 三段占比堆叠图     | 发现「历史膨胀挤压检索内容」等结构性问题          |
| 检索耗时                   | 线上     | retrieval latency_ms                   | 切分/索引方案变更的性能面                         |

### 5.3 指标与调优动作的映射(闭环)

```
Recall@K 低 + 零结果率高     → 调切分(size/overlap/语义切分)或 embedding 模型
Recall@K 高 + Precision 低   → 调阈值/top_k,或加重排序
RAG 注入率低                 → 调 search_docs 工具描述(prompt 工程侧)
history 占比过高             → 上历史压缩/窗口策略(context 干预,第二阶段)
prompt token 涨 + 通过率跌   → 回滚模板版本(版本化直接支持)
```

---

## 6. rag.py 参数化(被调优对象的最小改造)

- `chunk_text(size, overlap)`、`search_chunks(top_k)`、`tools/rag.py` 的阈值
  改为从内存策略对象读取:`{"strategy": "chunk600_ov80_cosine", "size":600, "overlap":80, "top_k":3, "threshold":0.3}`;
- 策略对象由 contexteng 维护(环境变量初始化,API 可改),检索事件记录 `strategy`
  字段——同一时段不同策略的指标可分组对比(A/B 的基础);
- 加 `POST /v1/documents/rebuild` 重建索引(按新策略重切+重 embedding),
  离线评测对比后再切换线上策略。

---

## 7. 前端改造(ServerManegeUI)

### 7.1 菜单分组

AdminLayout 侧边栏从平铺改为分组(沿用 Element Plus `el-sub-menu`,
现有 Dashboard/Logs 等保持平铺不动):

```
Prompt 工程
├── Prompt 模板    /prompt/templates   (perm: prompt:manage)
└── Prompt 监控    /prompt/metrics     (perm: prompt:view)
Context 工程
├── 检索与快照     /context/events     (perm: ctx:view)
└── Context 监控   /context/metrics    (perm: ctx:view)
```

### 7.2 页面设计(沿用现有 Dashboard 的 stat-card + 图表 + 表格模式)

**Prompt 模板页**:左树(分组→模板)右编辑区;版本下拉切换对比(内容 diff)、
「激活」「停用」按钮;编辑区支持 `{{var}}` 变量高亮与说明表。

**Prompt 监控页**:

- 顶部 stat 卡:今日调用、活跃模板数、平均 prompt token、最近回归通过率;
- 中部:版本分布堆叠柱状图(按天)、prompt token 趋势折线(按版本分色);
- 底部:模板明细表(模板/版本/调用量/token 均值/耗时/通过率),支持点击钻取。

**检索与快照页**:Tab 切换「检索事件」/「Context 快照」。

- 检索事件:过滤器(时间/零结果/用户)+ 表格;行展开显示命中 chunk 与分数条;
  零结果行提供「回收为评测用例」按钮(写 cx_eval_cases);
- Context 快照:表格 + 行展开显示组成占比横条图 + 注入 chunk 列表。

**Context 监控页**:

- 顶部 stat 卡:检索命中率、零结果率、平均最高相似度、context p95 token;
- 中部:相似度分数直方图、context token 趋势(均值+p95 双折线)、
  组成占比堆叠面积图、Recall@K/Precision@K 评测趋势线(离线点);
- 底部:零结果 query 榜 TOP N 表格(带回收按钮)、低分检索事件榜。

### 7.3 配套改动

- `vite.config.ts`:新增代理 `/v1/pe`、`/v1/cx` → `http://localhost:6010`;
- NestJS `permission-codes.ts`:新增 `prompt:manage`(Prompt 模板管理)、
  `prompt:view`(Prompt 监控查看)、`ctx:view`(Context 监控查看)三个权限码并 seed;
  (预留的 `dept:knowledge` 仍留给未来知识库管理功能,不混用)
- 图表库与组件沿用项目现状(Dashboard 同款),不引入新依赖。

---

## 8. eval 包对接

- 新增 `suites/retrieval.json` 生成器:从 `cx_eval_cases` 导出(enabled 用例);
- `core/runners.py` 新增 `run_retrieval()`:直接调 `search_chunks()`(in-process,
  与线上一致),计算 Recall@K / Precision@K / 零结果率;支持 `--strategy` 参数
  指定检索策略,同一份 ground truth 对比多策略;
- `core/report.py` 输出后,新增一步把汇总指标 POST 到 `/v1/cx/metrics/report`
  (写 cx_metrics_daily 的 recall_at_k / precision_at_k),实现「离线指标上板」;
- regression / quality 套件报告同样上报,按模板当前版本归因写 pe_metrics_daily。

---

## 9. 实施分期

| 期                   | 内容                                          | 验收                                       |
| -------------------- | --------------------------------------------- | ------------------------------------------ |
| **P0 数据先行**      | pe*\*/cx*\* 建表;3 个钩子;检索事件 + 快照落库 | 正常对话后两表有数据,主链路无感            |
| **P1 Prompt 版本化** | pe 模板 CRUD + 激活热更新;usage 事件          | 改 DB 模板不动代码即生效,版本可回滚        |
| **P2 前端两组四页**  | §7 全部页面 + 权限码 + 代理                   | 页面数据与库表一致                         |
| **P3 评测闭环**      | retrieval 套件 + 报告上报 + 零结果回收        | 改 chunk size 后两次评测可对比出差异       |
| **P4 策略化**        | rag 参数化 + 重建索引 + 策略 A/B              | 同 ground truth 两策略指标分板展示         |
| **P5(后续)**         | context 干预(预算/裁剪/历史压缩)、阈值告警    | 另立计划;本次表结构已预留 truncated 等字段 |

## 10. 与未来拆服务的衔接

- pe*\*/cx*\* 零跨域 FK,拆库即拆服务;
- harness 钩子签名即事件契约,拆服务后 collector 实现从「本地写库」换成「HTTP 上报」,
  钩子处零改动;
- `/v1/pe/*`、`/v1/cx/*` 路径独立,整体平移到新服务后只需改前端代理目标。

!!!!**\_\_\_**-------
发现问题了，数据库中是不是有两种不同的模型表，D:\selfFile\python\vue3\v3agent\packages\model-gateway项目和D:\selfFil
e\python\vue3\v3agent\packages\ServerManegeUI项目用了不同的两张表，导致管理端新增了，客户端没能查到。
