# contexteng — Context 工程(现场记录者)

> Context 的观测/评测/调参闭环:只记录不干预(第一阶段定位)。约 1000 行,管理台 /v1/cx/* 的后端。

## 文件地图

| 文件 | 职责 |
|---|---|
| `models.py` | 4 张表:cx_retrieval_events / cx_context_snapshots / cx_eval_cases / cx_metrics_daily |
| `strategy.py` | 检索策略对象(chunk size/overlap/top_k/threshold),内存单例,API 热切换,A/B 基础 |
| `events.py` | 三类事件 TypedDict 契约(拆服务时即 HTTP payload,钩子零改动) |
| `collector.py` | 钩子实现:异步落库 + contextvar 请求上下文绑定 |
| `evaluator.py` | 离线评测:Recall@K / Precision@K / 零结果率,直接调线上 search_chunks(口径一致) |
| `metrics.py` | 看板聚合:零结果率/分数分布/p95/注入率/token 水位 |
| `api.py` | /v1/cx/* 路由(事件查询/快照/评测用例/评测触发/策略管理) |

## 三条钩子纪律(全模块遵守,collector.py docstring)

1. 所有上报 try/except 全捕获,**观测失败绝不影响主链路**
2. 落库用独立 session(不与请求 session 混用)
3. >5ms 的 DB 写入放 `asyncio.create_task` 后台

## 数据从哪来(接线关系)

- 检索事件 ← `tools/rag.py#search_docs` 每次调用上报
- Context 快照 ← `agent/loop.py#agent_node` 每次模型调用后回调(`_build_snapshot` 纯函数)
- prompt 使用事件 ← collector 从快照**派生**(同一次模型调用按 agent.system 模板归因——与 prompteng 共享一条数据)
- 请求上下文(user_id/conversation_id)← `main.py` 入口 `bind_request_context` 绑 contextvar

## 学习路径

1. `strategy.py`(36 行)先读——理解"策略即被调优对象"
2. `collector.py` 看钩子纪律与 contextvar 用法
3. `agent/loop.py#_build_snapshot` 对照看快照怎么算
4. `evaluator.py` 看离线评测为何要复用线上实现

## 优化切入点

- token 估算(len/1.6)→ 真实 tokenizer
- `_recent_rag_chunks` 是进程内弱状态,重启清零 → 可入 checkpoint 或 DB
- 干预能力(truncated 恒 0):历史裁剪/压缩策略是第二阶段方向
- 评测只有检索维度 → 可加端到端回答质量评测
