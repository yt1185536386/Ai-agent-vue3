# ai-service 架构拆解报告

> 范围:`packages/ai-service/app`(约 4000 行 Python,FastAPI)
> 定位:整个系统里唯一的"AI 应用层"——模型代理 + 服务端 Agent + RAG + 双工程化模块

---

## 0. 一句话总览

ai-service 对上暴露 **OpenAI 兼容接口**(NestJS/前端无需改协议),对下统一走 Java model-gateway 调模型;内部包含 **五套子系统**:

| 子系统 | 目录 | 一句话职责 |
|---|---|---|
| Agent 运行框架 | `agent/` | 手写 ReAct LangGraph 循环 + SSE 流 + prompt/消息加工 |
| 工具系统(function-calling) | `tools/` | 静态基础工具 + 闭包装配的 RAG 工具 |
| Prompt 工程 | `prompteng/` | 系统提示词模板的版本管理/热更新/使用归因 |
| Context 工程 | `contexteng/` | 检索策略 A/B、上下文快照观测、离线评测 |
| RAG 子系统 | `rag/engine.py` | 文档分块/embedding/向量检索(SQLite 起步) |

```
NestJS ──▶ /v1/chat/completions ──┬─ 带 tools/supports_tools ─▶ run_agent(ReAct 图)
                                  └─ 无 tools ───────────────▶ forward_upstream(直答)
管理台 ──▶ /v1/pe/*(Prompt 工程)  /v1/cx/*(Context 工程)
        ──▶ /v1/documents(RAG)   /v1/conversations(会话)  /v1/asr(语音)
```

## 1. 请求入口与双路径分流(main.py)

`/v1/chat/completions` 是唯一对话入口,鉴权(`require_service_key`:X-Service-Key + X-User-Id)后按两个条件分流:

```
body.tools 或 body.use_agent,且 provider.supports_tools ─▶ run_agent()   服务端 Agent
其余                                                    ─▶ forward_upstream() 直答
```

入口处做的三件事:

1. **身份注入**:provider 字典拷贝并注入 `user_id / username / request_id`,后续所有模型调用透传给 Java 网关做计量
2. **观测上下文绑定**:`cx_collector.bind_request_context()` 把 user_id/conversation_id 放进 contextvar——工具与钩子内直接读,**不穿透改 agent 运行框架的函数签名**
3. **请求体预处理**(`agent/preprocess.py`):时间系统消息注入(纠偏模型日期幻觉)、来源联网搜索开关、思考模式规整(THINKING_MODELS 名单外剔除 enable_thinking 防上游报错;支持思考的模型默认补 False,显式 true 才开)

**直答路径**(`forward_upstream`):LangChain ChatOpenAI 直调,SSE 输出 token/reasoning 事件;无 checkpoint,推理上下文靠前端全量重发;展示轨道照常落库。

## 2. Agent 核心:手写 ReAct 循环(agent/loop.py)

没有用 `create_react_agent` prebuilt,而是手写等价 LangGraph 图(便于教学与定制):

```
          ┌─────────────────────────┐
          ▼                         │ tools 结果回灌
START → agent 节点(模型决策) ──有 tool_calls──▶ tools 节点(ToolNode 执行)
          │ 无 tool_calls
          ▼
         END
```

三个关键机制(源码注释原话):
1. **MessagesState reducer 累加**:节点只返回增量 `{"messages": [新消息]}`,LangGraph 自动 append——状态流转的本质
2. **bind_tools**:工具 schema 挂到模型上,输出的 `tool_calls` 字段成为条件边路由依据
3. **ToolNode**:执行 tool_calls 并把结果包成 ToolMessage 追加回状态

### 2.1 agent_node 细节

- 每轮把**全部累积历史**发给模型;系统提示(`agent_system_prompt()`:当前时间 + 规则块)**调用时临时前置,不写进图状态**——避免 checkpoint 里逐轮累加过期提示
- 模型调用完成后回调 **context 快照观测器**(token 组成/耗时/是否 RAG),失败静默,绝不影响主链路

### 2.2 Checkpoint 持久化(推理轨道)

- `AsyncSqliteSaver` → `checkpoints.db`(进程级懒初始化,uvicorn 重启不丢)
- conversation_id 即 LangGraph `thread_id`,每会话一条状态链
- 老会话一次性回填:首次遇到只有 messages 表历史的会话,把展示轨道投影为推理上下文,之后 checkpoint 接管

### 2.3 HITL 人机回环(interrupt/resume)

- 写操作类工具内部调 `langgraph interrupt()` 暂停图,状态落盘
- 前端审批卡片点「批准/拒绝」→ 请求带 `body.resume.decision` → 服务端构造 `Command(resume=决策)` **从断点恢复**(不重跑入口,不重读 messages);多个并行挂起的 interrupt 逐个送达同一决策
- 流结束时图若挂在 interrupt 上,补发 `approval_request` SSE 事件(含待审批明细);非流式撞 interrupt 则提示改用流式审批

### 2.4 regenerate 时间旅行分叉(main.py `_fork_for_regenerate`)

- 定位规则:截断后剩余 user 消息数 N → 在 checkpoint 历史(新→旧)中找「human 总数 == N 且末尾为 human」的最近快照,用其 checkpoint_id **分叉重跑**
- 顺序:先定位再截断——定位失败展示轨道不动、两轨不分叉;截断失败显式报错(常规落库 fail-soft,唯截断例外)
- 顺带修了旧版隐性 bug:旧「尾部空消息重跑」会让模型仍记得被删轮次

## 3. Function-calling 工具系统(app/tools/)

### 3.1 工具清单

| 工具 | 类型 | 说明 |
|---|---|---|
| `get_weather` | 静态 | wttr.in 实时天气,中文描述 |
| `calculator` | 静态 | AST 白名单求值(七种运算),防 eval 注入 |
| `get_current_time` | 静态 | 确切日期时间 |
| `query_bus_route` | 静态 | 高德 API(AMAP_API_KEY 未配置时返回可读提示) |
| `search_docs` | 动态装配 | RAG 检索,见 §3.3 |

历史上的仓库工具组/用户权限工具组/守门子图已随 2026-08 权限重构移除,现 Agent = 基础工具 + (有 embed 配置时)RAG 工具。

### 3.2 工具设计规范(代码即教材)

- **docstring 是写给模型的使用说明书**:何时调用、参数格式、何时不调,写得越准调用准确率越高(`query_bus_route` 甚至注明"从A到B怎么坐车不要用本工具")
- **错误返回可读文本**而非抛异常:让模型自行向用户解释,工具调用永不崩溃主链路

### 3.3 RAG 工具的四个精巧点(tools/rag.py)

1. **闭包注入**:不通过全局状态拿 user_id/embedding 配置,构建时闭包捕获
2. **Agent 自主决策**:RAG 从"强制注入上下文"改为工具化——模型自己判断要不要查文档
3. **策略热读**:top_k/threshold 每次调用现读 `contexteng.strategy`(支持 API 热切换做 A/B)
4. **DB 模板覆盖工具描述**:`rag.search_docs` 模板激活时覆盖 docstring——改模板即改模型调用行为,无需发版

## 4. SSE 流式协议(agent/stream.py)

前端已剥离 LangChain,直接消费自定义事件流:

```
event: token            # 正文 token(与落库逐字一致)
event: reasoning        # 思考过程(qwen3/deepseek/k3 的 reasoning_content)
event: tool_start       # {name, args} 工具调用开始
event: tool_end         # {name, result} 工具结果
event: approval_request # HITL 待审批明细
event: done / [DONE]    # 结束
```

实现要点:

- 基于 `astream_events(version="v2")`;**子图内部事件按 checkpoint_ns 含 `|` 过滤**(守门分类器的流永不泄漏成正文),tags `guardrail_internal` 兜底
- `reasoning` 在 tool_calls 判断**之前**提取——工具决策帧也带思考 token
- 工具进行中丢弃中间文本(模型"我先去查"之类),`in_tool` 状态防重复 tool_start
- `collector` 容器累积正文,服务端落库与用户所见**逐字一致**,断连也有半条消息
- **卡片钩子解耦**:`register_card_hook(tool_name, hook)`——业务工具的结构化结果转前端交互卡片事件,业务知识不进 agent 运行框架

## 5. 持久化双轨制(persistence.py)

| 轨道 | 存储 | 权威性 | 失败策略 |
|---|---|---|---|
| 推理轨道 | checkpoints.db(SQLite) | 推理上下文唯一权威 | — |
| 展示轨道 | MySQL messages/conversations | 前端气泡唯一权威 | fail-soft(打日志继续) |

- 两轨写入全在服务端;前端只带本轮新消息
- 用户消息**进图前**落(图失败也不丢);助手消息流结束(正常/终止/异常)落;终止一字未发补"已终止回答";纯审批卡片轮次空气泡不落
- attachments 剥离 text 大字段防老会话回填时二次拼接

## 6. Prompt 工程(prompteng/)

- **模型**:`pe_templates`(key/group/status)+ `pe_template_versions`(draft/active/archived)+ `pe_usage_events`(按模板×版本归因调用量/token/耗时)+ `pe_metrics_daily`(离线回归通过率)
- **生命周期**:新建即 v1 draft → add_version 提交 draft(不影响线上)→ activate(旧版本归 archived + 刷缓存热生效)→ disable 回退代码默认;active/archived 不可编辑、active 不可删
- **热生效机制**:`_CACHE` 内存缓存是主链路唯一读取点(load_content 同步无 IO);`refresh_cache()` 在启动/激活/停用时重建,并对 `rules.*` 模板调用 `register_rules()` 热更新规则块
- **渲染安全**:`{{var}}` 简单文本替换,**刻意不用 Jinja**(避免模板注入);`agent.system` 支持 `{{time}}`/`{{rules}}` 变量
- 管理面 `/v1/pe/*`(require_admin_user):模板 CRUD + metrics/overview 看板 + 最近装配记录(内存环形缓冲 200 条)

## 7. Context 工程(contexteng/)

围绕"检索质量与上下文水位"的可观测/可评测/可调参闭环:

- **策略对象**(strategy.py):chunk size/overlap/top_k/threshold 内存单例,API 热切换,每次检索事件记录 strategy 标识 → **同一时段不同策略分组对比(A/B 基础)**
- **事件采集**(collector.py):三条纪律——try/except 全捕获(观测永不影响主链路)、独立 session、>5ms 的落库放 `asyncio.create_task` 后台
  - 检索事件 `cx_retrieval_events`:query/命中/分数/耗时/零结果
  - Context 快照 `cx_context_snapshots`:每轮模型调用的 token 组成(system/history/tool 估算,总 token 用 usage 精确值)+ rag_chunk_ids
  - 派生 `pe_usage_events`:同一次模型调用按 `agent.system` 模板归因(两个工程模块共享一条数据)
- **离线评测**(evaluator.py):对 cx_eval_cases 跑 Recall@K / Precision@K / 零结果率,**直接调线上同一 search_chunks 实现**(口径一致),结果 upsert `cx_metrics_daily` 上板;重建索引 `/v1/documents/rebuild` 配合策略 A/B
- 指标聚合(metrics.py):零结果率/分数分布/p95 耗时/注入率/token 水位

## 8. RAG 子系统(rag.py)

- 存储:SQLite(chunks 表,embedding JSON 序列化)——注释明确"后续可换 pgvector/Milvus/Chroma,接口不变"
- 流程:`_parse_text`(多 mime 文本抽取)→ `chunk_text`(策略参数切分)→ `embed_texts`(OpenAI 兼容 /embeddings)→ 余弦相似度检索 → threshold 过滤
- 端点:上传 `/v1/documents`、直查 `/v1/rag/search`(前端也可直接调)、按新策略全量重建 `/v1/documents/rebuild`(事务内先删后插;文档多时应改后台任务)

## 9. 其余能力

- **模型来源注册表**(providers/registry.py):以 Java 网关 channels 表为唯一数据源(15s TTL + 未命中强刷,查库失败保留旧缓存,首部署回落环境变量);渠道真实地址/密钥永不下发——调用统一经网关,X-Channel-Key 路由
- **ASR**:`/v1/asr/transcribe` 语音转文本
- **会话 CRUD**:`/v1/conversations` 列表/新建/详情/删除/追加消息/重命名
- **健康检查**:`/health`

## 10. 架构亮点与改进建议

**亮点**(可复用的设计模式):

1. **裸钩子注入**:agent 运行框架只定义 `set_template_loader / set_prompt_observer / set_context_observer` 注入点,不 import 业务模块——运行时在 agent/assembly.py `init_observability()` 接线,将来拆服务时事件 TypedDict 即 HTTP payload,钩子零改动
2. **观测失败静默纪律**:全部上报 try/except 全捕获,主链路永不因观测挂掉
3. **双轨持久化 + fail-soft 分级**:常规落库可容忍失败,唯两轨一致性敏感操作(截断)显式报错
4. **一切热可调**:prompt 模板、检索策略、工具描述全部 DB 驱动热生效
5. **contextvar 传请求上下文**:避免层层改签名,异步安全

**改进建议**(按优先级):

| 项 | 现状 | 建议 |
|---|---|---|
| 无 HITL 写操作工具 | interrupt 机制完备但没有注册任何写操作工具 | 加一个带 interrupt 的示例写工具,打通审批闭环验证 |
| token 估算粗糙 | len/1.6 经验系数 | 接 tiktoken/真实 tokenizer |
| RAG 全量重建同步执行 | 文档多会超时 | 后台任务 + 进度查询 |
| embed_texts 每次新建 AsyncClient | rag/engine.py 内联 httpx client | 复用 lifespan 里 app.state.http |
| 直答路径无 checkpoint | regenerate 只截断展示轨道 | 与 Agent 路径统一(或明确标注产品边界) |
| deps 鉴权偏弱 | 管理面仅要求 X-User-Id 非空 | 细粒度权限码(ctx:view 等)在 ai-service 侧落地校验 |
