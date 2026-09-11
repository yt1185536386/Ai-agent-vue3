# AI 学习路线：LangChain 与 Agent 进阶

> 基于 `v3agent/packages` 项目现状整理。
> 前提：项目已经接入 LangChain(`ChatOpenAI`)与 LangGraph(`create_react_agent`),
> 本文档的目标不是"从零开始学",而是**从"会调用现成封装"到"懂原理、能手写"**。

---

## 〇、现状盘点（你已经在哪）

`ai-service/app/agent.py` 已具备：

| 已有能力 | 位置 | 深度 |
|---|---|---|
| LangChain 模型封装 `ChatOpenAI` | `build_chat()` | 会调用 |
| LangGraph 预构建 ReAct Agent | `build_agent()` → `create_react_agent` | 黑盒使用 |
| 流式事件 `astream_events(v2)` → 自定义 SSE | `run_agent_stream()` | 已实现 token/tool_start/tool_end |
| 工具定义 `@tool` | `get_weather` | **模拟数据,未接真实 API** |
| RAG 检索注入 | `main.py` chat_completions | 强制注入,非 Agent 自主决策 |
| 会话/消息持久化(MySQL,按用户隔离) | `db.py` + NestJS 代理 | 已完成 |
| 用户态模型/来源偏好 | `user_chat_settings` 表 | 已完成 |

**核心判断：框架已进场,但深度很浅。** 工具是假的、Agent 是一行生成的黑盒、RAG 与 Agent 是两条互不相干的路径。

---

## 一、第一阶段：把 Agent 写实（1~2 天)

### 1.1 真实工具替换 mock ✅(2026-07-28 完成)

- [x] `get_weather` 接真实天气 API(选了 wttr.in,免 key;高德/心知需申请 key)
- [x] 新增工具:`calculator`(AST 白名单安全求值,拒绝任意代码执行)、`get_current_time`
- [x] **重点学习点**：`@tool` 的 docstring 就是给模型看的"使用说明书"。
  同一个工具,描述写"获取天气"和写"当用户询问某城市实时天气时调用,参数 city 为中文城市名",
  模型的调用准确率天差地别。**工具描述 = 提示词工程的一部分**。
- [x] 实践要点二:**工具失败返回可读错误字符串**(如"天气查询出错:...请向用户说明"),
  让模型自行向用户解释,而不是抛异常崩掉整个 ReAct 循环

```python
@tool
async def get_weather(city: str) -> str:
    """当用户询问某个城市的实时天气时调用。
    city: 中文城市名,如 "北京"、"上海"。不要传省份或国家。"""
    # httpx 调真实 API,失败时返回可读错误让模型自行补救
```

### 1.2 RAG 工具化（思维转变的关键一步）✅(2026-07-28 完成)

- [x] 把检索改造成 `search_docs` 工具(闭包注入 user_id + embedding 配置,见 `build_rag_tool`):

```python
@tool
async def search_docs(query: str) -> str:
    """当用户的问题可能涉及其上传过的文档资料时调用,
    传入检索关键词,返回最相关的文档片段。闲聊、常识问题不要调用。"""
```

- [x] 从 `chat_completions` 中移除强制注入逻辑,带 `use_agent`/`tools` 时由 Agent 自主决策
- [x] 前端新增「Agent」开关(chip),请求带 `use_agent: true`;关闭时保持纯模型直答
- **核心理念**：从"流程编排"（开发者写死每一步）转向"自主决策"（模型按场景选工具）。
  这是 Agent 设计的分水岭。

### 1.3 排坑记录(实施中真实遇到,比工具本身更值得记住)

1. **来源自带的 `enable_search` 与工具自治冲突**:百炼 `enable_search=true` 时,
   模型直接用内置联网搜索回答,完全绕过 `bind_tools` 挂载的工具。
   解决:Agent 路径强制 `body.pop("enable_search")`——联网检索应由显式工具完成。
   **教训:能力重复时,模型永远选"更省事"的那条路;架构上要保证每个能力只有一个入口。**
2. **公司网关 k3 不吐 tool_calls**:`bind_tools` 直连百炼 qwen-plus 正常返回 tool_calls,
   但公司网关 k3 直接答"我无法调用工具"(且不报错)。调试分层法:进程内直接 `bind_tools` 测试
   → 排除 LangChain 层 → 定位到网关/模型能力差异。
3. **uvicorn --reload 假重载**:WatchFiles 日志显示 "Reloading..." 但进程未真正重启,
   接口一直跑旧代码(`if body.get("tools")` 旧路由)。教训:重载后看日志确认
   "Started server process" 再测;存疑时直接杀进程冷启动。
4. **Git Bash curl 中文 body 乱码**:Windows 控制台 GBK 会把 `-d` 里的中文编成乱码发给模型,
   表现为"模型答非所问"。调试用 Python httpx 发请求。

**阶段验收**(全部通过,完整链路 前端→NestJS→ai-service→模型):
问"上海今天天气怎么样" → `tool_start: get_weather` → wttr.in 真实数据;
问"(123+456)*789" → `tool_start: calculator` → 456831;
问"部署服务器在哪个机柜" → `tool_start: search_docs` → 命中上传文档。

---

## 二、第二阶段：手写 LangGraph,扔掉 prebuilt（2~3 天,核心环节)✅(2026-08-03 完成)

`create_react_agent` 一行搞定虽然方便,但学不到东西。
用 `StateGraph` 手写同样的 ReAct 循环：

```
                ┌──────────────────────────────┐
                ▼                              │
START → agent 节点(模型决策) → 条件边:有 tool_calls? → tools 节点(执行工具)
                    │                              │
                    ▼ 无 tool_calls                └─ 回到 agent 节点
                   END
```

### 2.1 要实现的最小骨架

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

def make_agent(chat, tools):
    chat_with_tools = chat.bind_tools(tools)

    async def agent_node(state: MessagesState):
        resp = await chat_with_tools.ainvoke(state["messages"])
        return {"messages": [resp]}

    def should_continue(state: MessagesState):
        last = state["messages"][-1]
        return "tools" if last.tool_calls else END

    g = StateGraph(MessagesState)
    g.add_node("agent", agent_node)
    g.add_node("tools", ToolNode(tools))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile()
```

### 2.2 手写一遍能真正理解的事

- **状态怎么流转**：`MessagesState` 的 messages 是累加的（reducer),每轮节点返回增量
- **`ToolNode` 干什么**：执行 tool_calls → 生成 ToolMessage 追加到状态
- **条件边怎么路由**：模型输出的结构化字段（tool_calls）决定下一步走向
- **循环怎么终止**：模型不再发起 tool_calls 即出循环
- 之后所有复杂 Agent(规划、反思、人机回环、多 Agent)都是这个骨架的扩展

### 2.3 替换验证 ✅(2026-08-03 完成)

- [x] 用手写 graph 替换 `build_agent()` 中的 `create_react_agent`(`make_agent()`,见 `agent.py`)
- [x] `run_agent_stream` 的 SSE 事件流行为保持不变（前端无感)
- [x] 对比前后 `astream_events` 输出,理解 prebuilt 帮你隐藏了什么
      (验证脚本:`ai-service/test_handwritten_agent.py`,同题双跑输出一致)

**阶段验收**：同一个天气问题,手写 graph 与 prebuilt 输出一致;能在 graph 里加 `print`/日志看清每一轮循环。

---

## 三、第三阶段：上下文工程（1~2 天)

### 3.1 摘要记忆（应对 context window 上限)

- [ ] 每 N 轮（如 20 条消息）把旧消息压缩成 summary:
  调一次模型「把以下对话压缩成 200 字摘要」,存到 conversations 表新字段
- [ ] 构建发给模型的 messages 时:`[summary system 消息] + [最近 K 条原文]`

### 3.2 长期记忆（跨会话)

- [ ] 基于已有的 `user_chat_settings` 表扩展（或新建 `user_memories` 表）:
  让 Agent 用一个 `save_memory` 工具主动记录用户偏好（"记住我喜欢简洁的回答")
- [ ] 每次会话开始把该用户 memories 注入 system 消息

### 3.3 思考过程流式透传 ✅(2026-08-04 完成)

- [x] 现状：`reasoning_content` 只有非流式路径透传（`forward_upstream` 非流式分支）
- [x] `run_agent_stream` / 流式聊天路径补一个 `reasoning` SSE 事件,前端折叠展示思考过程
- [x] 排坑:langchain_openai 1.4 起不再把 delta.reasoning_content 提取进
      additional_kwargs,补了 `ThinkingChatOpenAI` 子类重写 `_convert_chunk_to_generation_chunk`
      把它放回去(流式/非流式/Agent/直答四条路径统一受益)

**阶段验收**：连续对话 30 轮不爆 context;换会话后模型仍记得你的偏好;流式响应能看到思考链。

---

## 四、第四阶段：工程化（按需)

- [ ] **MCP(Model Context Protocol)**：把工具从"写死在 agent.py"变成标准协议接入。
  2026 年工具生态主流方向,学会后任何 MCP server(文件系统/数据库/GitHub)即插即用
- [ ] **可观测性**：接 LangSmith,或自建 `tool_call_logs` 表记录每次工具调用的输入/输出/耗时。
  **没有 trace 就没法调优 Agent**——不知道为什么没调工具、为什么调错参数时只能靠猜
- [ ] **简单 eval**：固定 10~20 个测试问题(该调工具的 / 不该调的 / 需要 RAG 的),
  每次改 prompt 或工具后跑一遍回归对比

---

## 五、不建议现在做的

| 方向 | 原因 |
|---|---|
| 多 Agent(supervisor/swarm) | 单 Agent + 好工具没玩透前,多 Agent 只会放大调试难度 |
| 换向量数据库(pgvector/Chroma) | RAG 先工具化跑通,数据量真大了再换,接口已预留 |
| 微调模型 | 提示词 + 工具能解决的问题不要上微调 |

---

## 六、节奏总览

```
第一阶段(写实)      第二阶段(手写)      第三阶段(上下文)     第四阶段(工程化)
真实工具           StateGraph         摘要记忆            MCP
RAG 工具化    →    手写 ReAct    →    长期记忆       →    可观测性
                  替换 prebuilt      reasoning 流式       eval 回归
  1~2 天            2~3 天             1~2 天              按需
```

前两个阶段走完,LangChain/LangGraph 的核心就扎实了;后面都是应用题。

---

## 附：对应代码位置速查

| 主题 | 文件 |
|---|---|
| Agent / 工具 / 流式 | `ai-service/app/agent.py` |
| 对话入口 / RAG 强制注入 | `ai-service/app/main.py` → `chat_completions` |
| RAG 检索实现 | `ai-service/app/rag.py` |
| 会话持久化 | `ai-service/app/db.py` |
| 用户态模型偏好 | `NestJS/src/chat/chat.service.ts` + `user-chat-setting.entity.ts` |
| 前端 SSE 消费 | `my-vue-app-ts/src/axios/sse.ts` + `mixin.ts runAgent` |
