# 完整 Chatflow 详解(学习版)

一条用户消息从浏览器发出,到答案逐字渲染回来的**全链路**。
本文把每个环节「在哪个文件、做了什么、为什么这样设计」串起来,配合
[项目架构说明.md](项目架构说明.md)(模块职责)阅读。

## 全景图

```
① 前端发消息          my-vue-app-ts  AgentMode/mixin.ts  runAgent()
② Vite 代理           /api → localhost:6011
③ NestJS 网关         chat.controller.ts:JWT 鉴权 → 注入内部头转发
④ ai-service 入口     main.py:preprocess() → 分流(Agent / 直答)→ 用户消息落库
⑤ 守门子图+ReAct 循环 guardrail 子图(越权拦截)→ loop.py:决策 ⇄ 工具,可中断审批
⑥ SSE 事件回传        harness/stream.py(子图事件过滤)→ NestJS pipe → 浏览器
⑦ HITL 审批分支       interrupt → checkpoints.db → 审批卡片 → resume
⑧ 前端渲染 + 服务端落库 mixin.ts streamChat() → index.vue;消息由服务端统一持久化
```

> 2026-08 重构:会话持久化**所有权收敛到服务端**——checkpoint 是推理轨道
> 唯一权威,messages 表是展示轨道唯一权威;前端只发本轮新消息、不再逐条落库,
> `tail_new_messages` 断点去重机制已删除;守门从图外函数重构为图内子图。

---

## ① 前端发消息

**文件**:`my-vue-app-ts/src/view/AgentMode/mixin.ts` → `runAgent()` / `streamChat()`

用户敲一句话,前端做三件事:

```js
await streamChat(conv, assistantMsg, {
  model: currentModel.value,
  messages,                  // Agent 模式:仅本轮新消息(通常 1 条 user);
                             // 直答模式:全量历史(无 checkpoint,上下文靠重发)
  stream: true,
  enable_thinking: thinkingEnabled.value,  // 显式布尔:不传上游默认开思考
  use_agent: true,           // 声明走服务端 Agent
  conversation_id: conv.id,  // 关键:作为 LangGraph thread_id,HITL 断点靠它定位
  attachments,               // 本轮 user 消息的展示元数据(服务端落库用;
                             // 文档文本已拼进 content,图片 base64 不落库)
});
```

**学习要点**:
- 前端**不含任何 LangChain 代码**(已剥离),只发 OpenAI 兼容请求、收自定义 SSE;
- Agent 模式**只发本轮新消息**:推理上下文由服务端 checkpoint 提供,
  不再全量重发、不再需要服务端去重;
- 前端**不再逐条持久化消息**:用户/助手消息都由服务端在聊天流程中落库(见④⑧);
- `conversation_id` 是整个 HITL 的钥匙:审批暂停后,下一轮请求靠它找回断点。

## ② Vite 代理

**文件**:`my-vue-app-ts/vite.config.ts`

`/api` 前缀代理到 `http://localhost:6011`(`NESTJS_PORT`),开发环境免去跨域。
SSE 流式响应经 http-proxy 默认逐 chunk 透传,不缓冲。

## ③ NestJS 网关

**文件**:`NestJS/src/chat/chat.controller.ts` → `completions()`

```ts
// 1. JwtAuthGuard 先校验登录态(请求进不了 controller 就被拦)
const upstream = await this.chatService.chatCompletions(body, user.userId);
// 2. chatService 注入内部头:X-Service-Key(内部密钥)+ X-User-Id(用户身份)
// 3. 流式:flushHeaders() 后 Readable.fromWeb(upstream.body).pipe(res) 直转
```

**学习要点**:
- NestJS 对对话请求是**纯转发**,不做任何 prompt 加工(那些已下沉到 ai-service);
- 它真正管的对话相关状态是「用户当前用哪个来源/模型」(`user_chat_settings` 表);
- **内部鉴权设计**:浏览器拿不到 `X-Service-Key`,ai-service 只信 NestJS,
  用户身份通过 `X-User-Id` 头传递——ai-service 的工具按它做数据隔离。

## ④ ai-service 入口与分流

**文件**:`ai-service/app/main.py` → `chat_completions()`

```python
body = preprocess(body, provider)   # harness/preprocess.py
if (body.get("tools") or body.get("use_agent")) and provider.get("supports_tools"):
    return await run_agent(...)      # → ⑤ Agent 路径
return await forward_upstream(...)   # → 直答路径
```

`preprocess()` 三件小事(`harness/preprocess.py`):
1. **注入当前时间**:纠正模型/网关自带的错误日期;
2. **enable_search**:按来源配置补联网搜索(但 Agent 路径会强制关掉,见⑤);
3. **enable_thinking 显式化**:思考型模型上游默认开思考,未显式传就补 `false`。

**直答路径**(`forward_upstream()`):无工具,`build_chat` 直接调模型,
SSE 只发 `reasoning` / `token` / `done` 事件。普通模式(userMode)也走这里。
推理上下文仍靠前端全量重发(此路径无 checkpoint);**落库规则与 Agent 路径相同**
(见下),regenerate 只截断展示轨、由前端重发截断后的历史。

**Agent 路径的会话持久化(所有权收敛,2026-08 重构)**:
`checkpoint = 推理轨道唯一权威,messages 表 = 展示轨道唯一权威`,
两轨以 `conversation_id == thread_id` 绑定,两端写入都在服务端:

1. **归属校验**:`conversation_id` 指向的会话必须属于当前 `X-User-Id`,否则 404;
2. **用户消息进图前落库**(`app/persistence.py`,fail-soft 打日志继续):
   图失败/终止用户消息也不丢,两轨顺序一致;
3. **推理上下文直接取 checkpoint**:本轮新消息追加进图即可,无需任何去重
   (老客户端全量重发时有一行守卫:checkpoint 已有历史则只认最后一条 human);
4. **老会话一次性回填**:checkpoint 无历史而 messages 表有(改造前的会话),
   把展示轨投影为推理上下文(文档文本拼接进 content、图片降级为占位符),
   之后 checkpoint 接管。

## ⑤ 守门子图 + ReAct 循环(Agent 核心)

**文件**:`ai-service/app/harness/loop.py` → `make_agent()`;守门子图在 `app/guardrail.py`

```
START → guardrail 子图(用户域守门)──拒绝──→ END
              │放行
              ▼        ┌──────────────────────────────┐
        agent 节点(模型决策) → 有 tool_calls? → tools 节点(执行工具)
                  │                              │
                  ▼ 无 tool_calls                └─ 结果回灌,再决策
                 END(最终回答)
```

**守门子图**(`app/guardrail.py` → `build_guardrail_subgraph()`,`GUARDRAIL_ENABLED`
且 user_id 非空时由 `build_agent()` 装配在 START 与 agent 之间):

```
screen(关键词初筛,零成本)
  ├─ 疑似 → classify_decide(LLM 意图精判 + 权限决策表 + 审计落库)
  │         ├─ 拒绝:拒绝文案作为 AIMessage 写入图状态,verdict=refuse → END
  │         └─ 放行:verdict=pass
  └─ 不疑似 → 放行
```

- 明显越权的用户管理请求**不进 ReAct 循环、不调工具、不触发审批卡片**;
  拒绝文案的下发见⑥(流末补发 token);
- fail-open:分类器异常/低置信度/守门自身异常一律放行——
  工具层权限检查与 NestJS 规则引擎仍是完整兜底链,守门只是前置优化;
- 审批恢复(Command resume)与 regenerate 分叉都从断点继续执行,
  **不重走入口子图**,天然不会被重复拦截。

ReAct 三个关键机制(对照代码注释理解):

1. **状态累加(reducer)**:`MessagesState.messages` 带 reducer,节点只返回
   增量 `{"messages": [新消息]}`,LangGraph 自动 append——这就是"状态流转";
2. **工具挂载**:`chat.bind_tools(tools)` 把工具 schema 交给模型,
   模型输出里的 `tool_calls` 字段成为条件边的路由依据;
3. **系统提示的注入时机**:`agent_node` 每轮决策时**临时前置**
   `[SystemMessage(时间+各领域规则), *历史]`,**不写入图状态**——
   否则每轮往 checkpoint 追加一条,越积越多,时间还会过期。

工具从哪来(`app/agent.py` → `build_agent()`):
`基础工具(天气/计算器/时间/公交)` + `仓库工具组` + `用户权限工具组` + `RAG 工具`,
模型在一个循环里自主选用——这就是为什么资产规则和用户规则在同一个 prompt 里:
**它们本来就是同一个 Agent 的两块业务知识**。

一个细节:Agent 路径**强制关闭来源自带的联网搜索**(`run_agent()` 里
`body.pop("enable_search")`),否则模型会绕过工具直接用内置搜索回答,
工具调用形同虚设。

## ⑥ SSE 事件回传

**文件**:`ai-service/app/harness/stream.py` → `run_agent_stream()`

图的执行被翻译成自定义事件流(`astream_events` 逐事件消费):

| 事件 | 触发时机 | 前端表现 |
|---|---|---|
| `reasoning` | 思考型模型吐 reasoning_content(含工具决策帧里的思考) | 思考面板流式展示 |
| `tool_start` | 模型输出 tool_calls 决策帧 | 步骤列表加一项,转圈 |
| `tool_end` | 工具执行完 | 步骤勾掉,收起 |
| `asset_card` / `user_card` / `option_card` | ~~特定工具返回结构化结果(钩子注册制) → 渲染勾选/单选卡片~~(2026-08 已随仓库/用户权限工具组移除) | 已移除 |
| `token` | 正文 chunk | 增量渲染正文 |
| `approval_request` | 流结束时图挂在 interrupt 上 | 渲染审批卡片 |
| `done` / `error` | 结束/异常 | 收尾 |

**学习要点**:
- 思考/正文分离:`reasoning` 与 `token` 分开累积,正文第一个 token 到达 =
  思考结束(前端自动收起思考面板)——思考型模型必须先想完再答,这是模型固有顺序;
- 卡片事件**不在 harness 里写死**:业务模块通过 `register_card_hook` 注册
  「工具结果 → 卡片事件」的转换函数,harness 只负责查表调用;
- **子图事件过滤**:`astream_events` 会把子图内部事件一并流出——守门分类器的
  意图 JSON/reasoning 若不作理会泄漏成正文 token。stream.py 按
  `langgraph_checkpoint_ns` 的 `|` 分隔符丢弃子图内部事件
  (父图节点事件是 `agent:<id>` 单段,子图内部是 `guardrail:<id>|classify_decide:<id>`),
  分类调用另打 `guardrail_internal` tag 双保险;
- **守门拒绝的下发**:图在子图内终结时全程无模型 token,stream.py 流末
  `aget_state` 检测 `verdict == "refuse"`,把子图写进状态的拒绝文案补发为
  `token` 事件——SSE 形状与正常回答一致,前端零改动;
- **collector**:`run_agent_stream` 把每个已发 token 同步累积进 collector,
  流收尾(正常/终止/异常)时由 main.py 落库助手消息——与用户所见逐字一致,
  终止时手里也有半条消息(见⑧);
- 传输路径上 NestJS(`pipe` 直转)、Vite 都不缓冲,所以思考是实时可见的。

## ⑦ HITL 审批分支(人机回环)

变更类工具(原仓库出/入/调/废、用户权限类等,2026-08 已移除)内部调 `interrupt()`:

```
模型调变更工具
  → 工具内 interrupt({action:"操作", detail:"操作明细"})
  → 图暂停,断点落 checkpoints.db(SQLite,uvicorn 重启不丢)
  → ⑥ 流尾补发 approval_request → 前端渲染审批卡片
  → 用户点「批准」→ 前端发新请求 {conversation_id, resume:{decision:"approve"}}
  → main.py 见到 resume.decision:不读 messages,
    用 Command(resume={interrupt_id: "approve"}) 从断点恢复
  → 工具拿到 decision == "approve" → 重新 SELECT FOR UPDATE 校验状态 → 执行
```

**学习要点**:
- 审批**不是模型层面的"请你确认"**,而是系统层的硬暂停——模型无法代替用户批准,
  这是 HITL 与"prompt 里让模型问一句"的本质区别;
- 恢复后**重新校验**再执行:审批可能等几分钟,期间库存可能已被别人改;
- `conversation_id` = thread_id:没有它,断点就找不回来;
- 审批拒绝时工具返回固定文案并(用户权限类)直插审计日志,全链路留痕。

## ⑧ 前端渲染 + 服务端落库

**文件**:`mixin.ts` → `streamChat()` 的 `onEvent` 分发 + `index.vue`;
落库在 `ai-service/app/main.py` + `app/persistence.py`

- `reasoning`/`token` 追加到 `assistantMsg.reasoning` / `.content`,
  120ms 节流渲染(`scheduleFlush`),底部自动滚动;
- 卡片事件已随业务工具组移除;当前 Agent 只保留通用工具 + RAG,不再渲染交互卡片;
- `token` 事件直接渲染正文。
- `finally` 兜底:任何结束路径都把转圈的步骤标记完成、停止 loading——
  **仅此而已,前端不再落库**;
- **消息持久化全部由服务端完成**(`persistence.py`,fail-soft):
  用户消息在④进图前落库;助手消息在流收尾时按 collector 累积的
  已发 token 落库——正常结束全量、前端终止带 `flags.aborted`
  (一字未发补「已终止回答」)、执行异常带 `flags.error`;
  守门拒绝文案经 collector 同一条管道落库;审批恢复产生的新回答亦然。
  历史回显(`GET /v1/conversations/{id}`)只读 messages 表,与 checkpoint 无瓜葛。

---

## 变体速查

| 场景 | 与主干的差异 |
|---|---|
| 直答(普通模式/来源不支持 tool_calls) | 跳过⑤,④直接调模型;SSE 只有 reasoning/token/done;推理上下文靠全量重发,落库规则与 Agent 路径相同 |
| 守门拦截(越权用户域请求) | 2026-08 已移除:原入口守门子图移除,越权与业务规则由 NestJS 规则引擎处理;当前 Agent 路径 = 普通 ReAct,无入口子图 |
| 重新生成 | 前端截断本地消息后发 `{messages: [], regenerate: {keep}}`;服务端截断展示轨到 keep,再用 `aget_state_history` 定位「末尾为 human 且 human 数=截断后 user 数」的最近 checkpoint **分叉重跑**——真正回到该时点(旧版"截断重发"下 checkpoint 仍含被删轮次,模型仍记得,是隐性 bug) |
| RAG | 不是独立链路,是⑤里模型自主调了 `search_docs` 工具 |
| 审批拒绝 | ⑦中 decision != "approve",工具返回取消文案,模型如实告知 |
| 删除会话 | messages 表级联删除 + `adelete_thread` 联动清 checkpoint(原为孤儿断点) |

## 一句话总结

> **Chatflow = 前端发本轮新消息 → NestJS 鉴权转发 → ai-service 加工分流、
> 用户消息落库 → ReAct 循环(可中断)→ SSE 事件流回来 →
> 前端渲染、服务端按已发 token 落库**;
> checkpoint 是推理轨道唯一权威,messages 表是展示轨道唯一权威;
> HITL、卡片、RAG、守门都是「ReAct 循环 + SSE」这两个环节上的分支。
