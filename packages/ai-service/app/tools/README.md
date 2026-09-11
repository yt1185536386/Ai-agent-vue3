# tools — Function-calling 工具系统

> Agent 能做什么事,全在这里注册。约 200 行,是动手扩展的第一现场。

## 文件地图

| 文件 | 职责 |
|---|---|
| `base.py` | 4 个静态基础工具:天气(wttr.in)/计算器(AST 白名单求值)/时间/公交(高德) |
| `rag.py` | `build_rag_tool`:闭包注入 user_id/embedding 配置的动态 RAG 检索工具 |
| `__init__.py` | 统一出口:BASE_TOOLS + build_rag_tool |

## 核心规范(改工具前必读)

1. **docstring 是写给模型的说明书**:何时调、参数格式、何时不调,写得越准调用率越高——看 `query_bus_route` 的反面示例("从A到B怎么坐车不要用")
2. **错误返回可读文本,不抛异常**:让模型自行向用户解释,工具崩溃不波及主链路
3. `__init__.py#BASE_TOOLS` 是全部静态工具的注册表;动态工具(RAG)由 `agent/assembly.py#build_agent` 按条件追加

## 学习路径

1. `base.py` 从上到下读完(只有 131 行),重点体会 docstring 写法与错误处理
2. `rag.py` 看四个精巧点:闭包注入 / Agent 自主决策(查不查文档模型说了算)/ 策略热读 / DB 模板覆盖工具描述
3. 对照 `agent/loop.py` 的条件边,理解 tool_calls 如何驱动循环

## 优化切入点

- **加新工具**:在 base.py 写 @tool + 注册进 BASE_TOOLS 即可,主链路零改动
- **加 HITL 示例写工具**:工具内部调 `langgraph interrupt()`,配合 stream.py 的 approval_request 事件打通审批闭环(当前机制空转中)
- 计算器可扩展三角函数/对数(AST 白名单加节点类型)
