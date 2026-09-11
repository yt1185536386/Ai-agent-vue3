# agent — Agent 运行框架

> 与业务无关的 ReAct 循环 + SSE 事件流 + 消息加工。系统的心脏,约 900 行。

## 文件地图

| 文件 | 行数 | 职责 |
|---|---|---|
| `client.py` | 56 | 模型客户端:ThinkingChatOpenAI(修补 reasoning 提取)+ build_chat(组装网关透传头) |
| `prompts.py` | 93 | 系统提示词:时间注入 + 业务规则注册表 + DB 模板注入点 |
| `loop.py` | 155 | **ReAct 循环核心**:手写 LangGraph 图 + SQLite checkpointer + context 快照观测 |
| `stream.py` | 163 | SSE 运行器:token/reasoning/tool_start/tool_end/approval_request 事件 + 卡片钩子 |
| `messages.py` | 58 | OpenAI dict ↔ LangChain 消息转换、content_format 标记 |
| `preprocess.py` | 48 | 请求体加工:时间注入/联网搜索/思考模式规整 |
| `assembly.py` | 62 | 业务装配:工具组选择(build_agent)+ 观测体系接线(init_observability) |

## 学习路径(按此顺序读)

1. **`loop.py`** — 先读懂模块 docstring 的图结构与"三个关键机制"(reducer 累加/bind_tools/ToolNode),这是理解一切的基础
2. **`client.py`** — 看调用怎么带 X-Channel-Key/X-User-Id/X-Request-Id 走 Java 网关
3. **`stream.py`** — 看 astream_events 如何裁剪成自定义 SSE 协议(重点:子图事件过滤、reasoning 提取时机)
4. `prompts.py` / `assembly.py` — 理解"裸钩子注入"设计:框架不 import 业务模块,启动时接线

## 优化切入点

- `loop.py#_est_tokens`:len/1.6 估算 → 接真实 tokenizer
- `stream.py`:工具进行中直接丢弃文本 token → 可考虑缓存为"过程说明"
- `loop.py`:守门子图(guardrail 参数)是预留接缝,可接入安全分类器
- HITL 机制完备但无写操作工具 → 在 tools/ 加一个带 interrupt 的示例写工具
