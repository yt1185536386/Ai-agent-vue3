# ai-service 源码学习地图

> FastAPI,约 4000 行。对外是 OpenAI 兼容接口,对内是五个子系统 + 地基。
> 每个子目录有各自 README(职责/文件地图/学习路径/优化切入点),这里是总纲。

## 目录与依赖关系

```
main.py ──────────────┐  入口:对话分流/会话/文档/ASR 路由
                      ▼
      ┌───────── core(地基:db + 鉴权)─────────┐
      │            │            │            │
      ▼            ▼            ▼            ▼
 providers    persistence      rag        agent(ReAct 循环+SSE)
 (模型来源)   (展示轨道落库)  (向量检索)   │
      │            │            │        ├── tools(function-calling 工具)
      │            │            └────────┤
      │            │                     ▼
      │            │        prompteng(Prompt 模板/版本/归因)
      │            │        contexteng(策略/快照/评测)
      └────────────┴──── 观测钩子反向注入 agent(裸钩子,启动时接线)
```

## 推荐学习顺序(由浅入深)

| 步骤 | 模块 | 行数 | 你会学到 |
|---|---|---|---|
| 1 | `core/` | ~260 | 两表模型、三类调用方的鉴权(最薄,先建立全局感) |
| 2 | `providers/` | ~115 | 渠道数据的缓存/兜底策略与"密钥不下发"安全约定 |
| 3 | `agent/`(loop + client) | ~210 | 手写 ReAct LangGraph:reducer/bind_tools/ToolNode 三机制 |
| 4 | `agent/`(stream) | ~163 | 自定义 SSE 协议怎么从 astream_events 裁剪出来 |
| 5 | `tools/` | ~200 | function-calling:docstring 写法、错误即文本、动态装配 |
| 6 | `persistence/` | ~110 | 双轨制:推理轨(checkpoint)vs 展示轨(messages) |
| 7 | `rag/` | ~170 | 向量检索全流程 + 为换 pgvector 预留的接口 |
| 8 | `prompteng/` | ~900 | 模板版本状态机、缓存热生效、按版本归因 |
| 9 | `contexteng/` | ~1000 | 观测三纪律、策略 A/B、离线评测口径一致 |

## 一次对话请求的完整旅程(主线剧情)

```
POST /v1/chat/completions (main.py)
 → core/deps 鉴权(NestJS 服务密钥)
 → providers/registry 选模型来源(channels 表,15s 缓存)
 → harness 加工:时间注入/思考模式(pipeline 在 agent/preprocess)
 → 带 tools? ── 是 → agent/loop ReAct 循环
 │                    ├─ agent/client 每轮调模型(经 Java 网关,带 X-Request-Id)
 │                    ├─ tools/ 模型自主决定调不调工具
 │                    ├─ agent/stream 裁成 SSE 事件流给前端
 │                    ├─ contexteng/collector 静默记录快照与检索事件
 │                    └─ prompteng 缓存提供系统提示词(DB 模板热生效)
 │                    └─ persistence/display 两轨落库
 └─ 否 → agent/client 直答(forward_upstream)
```

## 全局性优化专题(跨模块)

| 专题 | 涉及模块 | 说明 |
|---|---|---|
| 多实例缓存失效 | providers / prompteng | 15s TTL 与 _CACHE 都是进程内存 → Redis 广播 |
| token 精确计量 | agent/loop + contexteng | len/1.6 估算 → tokenizer |
| HITL 闭环 | tools + agent/stream | interrupt 机制完备但无写工具,加一个示例打通 |
| 向量库替换 | rag | search_chunks 签名不变,换 pgvector/Milvus |
| 管理面鉴权加固 | core/deps | 细粒度权限码落地 |
