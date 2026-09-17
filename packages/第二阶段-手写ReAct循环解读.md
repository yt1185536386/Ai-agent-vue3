# 第二阶段解读：手写 ReAct 循环,扔掉 create_react_agent 黑盒

> 对应学习路线第二阶段,基于 `ai-service/app/agent.py` 的 `make_agent()` 实现。
> 目标读者:已经会用 `create_react_agent(chat, tools)` 一行生成 Agent,但没看懂手写版在干什么的人。
> 阅读前提:知道"工具调用(tool_calls)"是什么——模型不真的执行工具,它只是输出一个"我想调用某工具"的结构化请求,由代码代为执行。

---

## 目录

1. [为什么要把黑盒拆开](#一为什么要把黑盒拆开)
2. [先建立整体图景:循环到底在循环什么](#二先建立整体图景循环到底在循环什么)
3. [四个零件逐个讲透](#三四 个零件逐个讲透)
4. [完整代码逐行注释](#四完整代码逐行注释)
5. [用一个例子走完全程](#五用一个例子走完全程)
6. [状态账本:messages 是怎么累加的](#六状态账本messages-是怎么累加的)
7. [create_react_agent 到底帮你藏了什么](#七create_react_agent-到底帮你藏了什么)
8. [手写之后能做什么(prebuilt 做不到的事)](#八手写之后能做什么prebuilt-做不到的事)
9. [常见疑问 FAQ](#九常见疑问-faq)
10. [动手验证清单](#十动手验证清单)

---

## 一、为什么要把黑盒拆开

第一阶段用一行代码就拥有了一个能干活的 Agent:

```python
create_react_agent(chat, tools)   # LangGraph 预构建的 ReAct Agent
```

它确实能跑:问天气会调 `get_weather`,问计算会调 `calculator`。但问题在于——**它为什么知道什么时候调工具、什么时候停?调完工具结果去了哪?** 这些全在盒子里。

不会拆黑盒的直接后果:一旦需求超出"模型决策→调工具→回答"这个固定模式(比如加审批、限圈数、多 Agent),就无从下手。

第二阶段的结论先行:**`create_react_agent` 内部没有任何神秘逻辑,它就是 2 个节点 + 3 条边的一张小图,25 行代码就能复刻。** 复刻完之后,所有复杂 Agent(规划、反思、人机回环、多 Agent)都只是这张小图的扩展。

---

## 二、先建立整体图景:循环到底在循环什么

Agent 的本质是**一个由模型输出驱动的循环**。以"长沙天气怎么样"为例:

```
第 1 圈:
  模型看到 [用户问题] → 输出"我要调 get_weather(city='长沙')"(tool_calls,不是回答)
  代码真的执行工具 → 拿到天气数据
  天气数据追加进对话记录

第 2 圈:
  模型看到 [用户问题 + 它自己要调工具 + 工具返回的天气] → 这次输出纯文字回答
  没有 tool_calls → 循环结束
```

三个关键认知:

1. **循环的燃料是"对话记录"**。每一圈,模型看到的都是截至目前累积的全部消息,而不只是最初那个问题。
2. **循环的方向盘在模型手里**。转几圈、每圈干什么、什么时候停,全部由模型每轮输出里有没有 `tool_calls` 决定。代码本身不含任何业务判断。
3. **代码只干两件事**:提供一个让消息不断累加的"容器",以及一套"下一步去哪"的路由规则。

LangGraph 就是用来表达这两件事的:**容器 = State(状态),路由 = 边(edge),干活的工位 = 节点(node)**。

```
                ┌────────────────────────────────┐
                ▼                                │
  START → 【agent 节点:调模型,做决策】              │
                │                                │
                ▼ 条件边:最后一条消息有 tool_calls 吗?
          ┌─────┴─────┐                          │
        有 │           │ 没有                     │
           ▼           ▼                          │
  【tools 节点:       END                        │
   执行工具,结果 ──────┘(结果追加进记录,回到 agent)
   追加进记录】
```

---

## 三、四个零件逐个讲透

### 零件 1:State(状态)—— 共享的"对话记录本"

```python
from langgraph.graph import MessagesState, StateGraph

g = StateGraph(MessagesState)
```

`MessagesState` 是 LangGraph 预定义好的状态结构,本质就是一个带 `messages` 列表的字典:

```python
{
  "messages": [
    HumanMessage("长沙天气怎么样"),      # 用户说的
    AIMessage(tool_calls=[...]),         # 模型说"我要调工具"
    ToolMessage("长沙当前天气:晴,29℃"), # 工具的执行结果
    AIMessage("长沙今天晴,29℃…"),       # 模型的最终回答
  ]
}
```

**它最重要的特性是 reducer(累加规则)**:`messages` 字段注册了"追加"规则——任何节点返回 `{"messages": [新消息]}`,LangGraph 会**追加**到列表末尾,而不是整体替换。

这意味着每个节点只需声明"我新增了什么",不用关心、也不允许弄丢历史。这是整个循环能转起来的地基。

> 类比:一本大家轮流写字的记录本。每人只往后加一行;谁拿到本子,都能看到前面所有人写的内容。模型的"记忆"不来自任何地方,就来自这个本子。

### 零件 2:节点(node)—— 循环里的两个"工位"

节点就是普通函数:输入是整个 state,输出是"要追加到 state 的增量"。整张图只有两个工位:

**工位一:`agent` 节点(大脑)**

```python
async def agent_node(state: MessagesState):
    resp = await chat_with_tools.ainvoke(state["messages"])  # 把整本记录发给模型
    return {"messages": [resp]}                              # 模型的回复,追加
```

它做的事朴素得惊人:把全部消息丢给模型,把模型说的话记到本子上。模型这一轮的输出只有两种形态:

- 带 `tool_calls`:"我还需要工具,帮我调 XX"
- 纯文本:最终回答

**工位二:`tools` 节点(手),用现成的 `ToolNode`**

```python
from langgraph.prebuilt import ToolNode

g.add_node("tools", ToolNode(tools))
```

`ToolNode` 是 LangGraph 给的现成零件,职责明确:

1. 读取本子上最后一条消息里的 `tool_calls`;
2. **真的执行**对应的工具函数(可能并行执行多个);
3. 把每个结果包成 `ToolMessage` 追加到本子。

注意它和 `create_react_agent` 的区别:`ToolNode` 虽然是预构建的,但它不再藏在黑盒里——它作为图上一个**可见、可替换**的节点摆在那里(以后想换成"执行前先写日志/先审批"的自定义节点,直接换掉它即可)。

### 零件 3:固定边(edge)—— 必然发生的"传送带"

```python
g.add_edge(START, "agent")     # 开始 → 先送大脑
g.add_edge("tools", "agent")   # 手干完活 → 必然送回大脑
```

固定边表示"无条件流转"。其中 `tools → agent` 这条边就是所谓的**结果回灌**:工具结果进了本子之后,必须让模型再看一眼,它才知道接下来该继续调工具还是给最终答案。

### 零件 4:条件边(conditional edge)—— 全图唯一的"如果"

```python
def should_continue(state: MessagesState):
    last = state["messages"][-1]            # 看本子上最后一行(模型刚说的)
    return "tools" if last.tool_calls else END

g.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
```

大脑每次说完话,都经过这个岔路口:

| 模型最新输出 | 路由结果 | 含义 |
|---|---|---|
| 带 `tool_calls` | 去 `tools` 节点 | 循环继续 |
| 纯文本 | 去 `END` | 循环终止 |

**这就是整个 Agent 的全部"智能调度"**:一个 if 判断。Agent 看起来会"自主规划多步",其实只是这个 if 被执行了多次。

---

## 四、完整代码逐行注释

`ai-service/app/agent.py` 中的 `make_agent()`:

```python
def make_agent(chat, tools):
    # ① 把工具的"使用说明书"(名字 + docstring + 参数 schema)挂到模型上。
    #    之后每次调模型,请求里都会带上 tools 字段,
    #    模型才有"输出 tool_calls"这个选项。第一阶段已验证:docstring = 提示词。
    chat_with_tools = chat.bind_tools(tools)

    # ② 工位一:大脑。输入整本对话记录,输出模型本轮的回复(增量)。
    async def agent_node(state: MessagesState):
        resp = await chat_with_tools.ainvoke(state["messages"])
        return {"messages": [resp]}

    # ③ 岔路口:检查模型最新一条消息是否携带 tool_calls。
    def should_continue(state: MessagesState):
        last = state["messages"][-1]
        return "tools" if last.tool_calls else END

    # ④ 声明图的"记录本"格式:MessagesState(messages 自动累加)。
    g = StateGraph(MessagesState)

    # ⑤ 摆上两个工位。
    g.add_node("agent", agent_node)
    g.add_node("tools", ToolNode(tools))

    # ⑥ 接三条传送带:
    g.add_edge(START, "agent")                 # 起点 → 大脑
    g.add_conditional_edges(                   # 大脑 → 岔路口(工具 or 结束)
        "agent", should_continue, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")               # 手 → 大脑(结果回灌,进入下一圈)

    # ⑦ 编译成可调用的 Agent。之后 ainvoke / astream_events 用法与 prebuilt 完全一致。
    return g.compile()
```

`build_agent()` 中的替换(行为等价,一行可切回):

```python
# 旧(prebuilt 黑盒):
return create_react_agent(build_chat(provider, model, body), tools)
# 新(手写图):
return make_agent(build_chat(provider, model, body), tools)
```

---

## 五、用一个例子走完全程

挑一个需要**两个工具、循环两圈**的问题:**"现在几点?3 小时后是几点?"**

```
START
  │
  ▼
【agent 节点·第 1 圈】
  本子:[Human: 现在几点?3小时后?]
  模型输出:AIMessage(tool_calls=[get_current_time()])
  追加后本子:2 条
  │
  ▼ should_continue → 有 tool_calls → tools
【tools 节点】
  执行 get_current_time() → "当前时间:…14:30"
  追加 ToolMessage → 本子:3 条
  │
  ▼ 固定边 tools → agent(回灌)
【agent 节点·第 2 圈】
  模型看到时间 14:30,但加法还没算 → 继续要工具
  模型输出:AIMessage(tool_calls=[calculator("14+3")])
  本子:4 条
  │
  ▼ should_continue → tools
【tools 节点】
  执行 calculator("14+3") → "14+3 = 17"
  本子:5 条
  │
  ▼ 回灌
【agent 节点·第 3 圈】
  两个结果都齐了,模型输出纯文本:
  "现在是 14:30,3 小时后是 17:30。"
  本子:6 条
  │
  ▼ should_continue → 无 tool_calls → END
结束。本子上最后一条消息就是最终答案。
```

观察三个要点:

- **模型自己决定转了 3 圈**。代码里没有任何"最多几圈/该调几个工具"的逻辑;
- **第 2 圈模型能看到第 1 圈的全部痕迹**(它自己要过工具、工具给了什么),这就是"上下文";
- 若用户在提问时就给了所有信息("3+5 等于几"且模型心算也行),模型第 1 圈就可能直接给文字 → 一圈就出循环。**圈数是结果,不是配置。**

---

## 六、状态账本:messages 是怎么累加的

把上面的过程画成"账本"视角,每一行是谁追加的:

| # | 消息类型 | 内容 | 谁追加的 |
|---|---|---|---|
| 1 | HumanMessage | "现在几点?3小时后?" | 调用方(入口) |
| 2 | AIMessage | tool_calls=[get_current_time] | agent 节点 |
| 3 | ToolMessage | "当前时间:…14:30" | tools 节点 |
| 4 | AIMessage | tool_calls=[calculator] | agent 节点 |
| 5 | ToolMessage | "14+3 = 17" | tools 节点 |
| 6 | AIMessage | "现在是14:30,3小时后17:30" | agent 节点(终) |

`should_continue` 永远只看**最后一行**:是 AIMessage 且带 tool_calls → 继续;否则 → 停。

这也解释了一个常见困惑:**"模型怎么记得前面查过什么?"** 模型没有任何跨请求记忆,每一圈都是无状态的一次调用;它"记得"是因为每次调用都把完整账本重新发给了它。token 消耗随圈数增长,原因也在这里(这是第三阶段"上下文工程"要解决的问题)。

---

## 七、create_react_agent 到底帮你藏了什么

答案:**藏的就是上面这一切,没有更多。** 它内部同样做了:

1. 建一个 messages 累加的 state;
2. 注册一个调模型的节点、一个 `ToolNode`;
3. 接同样的 START/条件/回灌三条边。

验证方式:第二阶段用 `test_handwritten_agent.py` 对同一问题双跑,手写图与 prebuilt 的 `astream_events` 事件序列逐帧一致——`on_tool_start(get_weather)` → `on_tool_end` → 最终文本,完全相同。

所以替换之后:

- 对外接口(`ainvoke` / `astream_events`)不变,`run_agent_stream` 的 SSE 输出不变,**前端无感**;
- 对内,循环的每一圈都变成你亲手写的代码,可以加日志、可以改路由。

> 顺带一个发现:LangGraph V1.0 起 `create_react_agent` 已标记弃用(迁往 `langchain.agents.create_agent`,V2.0 移除)。手写版不依赖它,天然免疫这类 API 变动。

---

## 八、手写之后能做什么(prebuilt 做不到的事)

手写图是一张**可以随便改的图纸**。几个典型扩展,都是"加一个节点 / 改一行路由"的事:

| 需求 | 改法 |
|---|---|
| 工具执行前人工审批(人机回环) | 在 `agent` 与 `tools` 之间插一个审批节点,配合 `interrupt` 暂停等待 |
| 防止死循环/控制成本 | `should_continue` 里加计数:超过 N 圈强制 `END` 或转"总结节点" |
| 工具调用审计日志 | 包一层自定义 tools 节点,执行前后写 `tool_call_logs` 表(第四阶段可观测性的入口) |
| 规划-执行分离 | 增加 plan 节点:先让模型出计划,再进 ReAct 循环执行 |
| 多 Agent | 注册多个 agent 节点(研究员/写手/校对),条件边按任务路由 |
| 长对话压缩 | 加一个摘要节点:账本超过阈值先压缩再继续(第三阶段摘要记忆的图内实现) |

共同模式:**所有复杂 Agent = 这张两节点小图 + 更多节点 + 更复杂的条件边。**

---

## 九、常见疑问 FAQ

**Q1:模型为什么会"知道"该输出 tool_calls?**
`bind_tools(tools)` 把每个工具的名字、docstring、参数 schema 塞进每次请求的 `tools` 字段。模型是被"告知"有工具可用的,而不是代码替它判断。这也是为什么第一阶段删 docstring 的实验会影响调用率——那本说明书就随请求一起发出去。

**Q2:`ToolNode` 不也是 prebuilt 吗?说好的扔掉 prebuilt 呢?**
扔掉的是"把整个循环打包"的黑盒(`create_react_agent`)。`ToolNode` 是图上一个**单职责、可见**的零件,和 `START`/`END` 一样是搭图的基础件。需要定制时(日志、审批、错误处理)可以随时换成自己写的节点。

**Q3:模型死循环一直要工具怎么办?**
当前骨架没有保护机制,靠模型自觉。工程上的做法就是在 `should_continue` 加圈数上限——这正是手写后才能做的事。

**Q4:`g.compile()` 编译了什么?**
把节点和边的声明编译成一个可执行的运行时(Runnable):负责按边调度节点、应用 reducer 合并状态、暴露 `ainvoke`/`astream_events` 等统一接口。之后用法和 prebuilt 产物完全一致。

**Q5:每圈都把全部消息发给模型,token 会不会爆?**
会,这是 ReAct 的固有成本,也是第三阶段"摘要记忆"要解决的:定期把旧消息压缩成摘要,只带摘要 + 最近 K 条进模型。

**Q6:为什么 `agent_node` 是 async 而 `should_continue` 是 sync?**
节点要做网络 IO(调模型),异步才能不阻塞事件循环;路由函数只读 state 做判断,纯 CPU、微秒级,不需要 async。LangGraph 两者都支持。

---

## 十、动手验证清单

理解是否到位,用下面几个动作自检(全部基于 `ai-service/` 目录):

- [ ] **双跑对比**:`.venv/Scripts/python test_handwritten_agent.py "长沙天气怎么样"`,确认手写图与 prebuilt 事件序列一致(已完成 ✅ 2026-08-03)
- [ ] **亲眼看循环**:在 `agent_node` 和 `should_continue` 里各加一行 `print`,问"现在几点,3小时后是几点",观察 agent 节点进 3 次、tools 节点进 2 次
- [ ] **一圈出循环**:问"你好",观察 tools 节点一次都没进,`should_continue` 直接返回 END
- [ ] **改路由**:把 `should_continue` 改成最多转 2 圈,问一个需要 3 个工具的问题,看强制终止的效果
- [ ] **端到端**:服务跑在 26010 时,从前端(26012)问天气,确认 SSE 事件流与替换前一致(已完成 ✅)

---

## 附:相关代码位置

| 内容 | 位置 |
|---|---|
| 手写 ReAct 循环 `make_agent()` | `ai-service/app/agent.py` |
| 替换点 `build_agent()` | 同上 |
| 双跑对比脚本 | `ai-service/test_handwritten_agent.py` |
| 学习路线总文档 | `AI学习路线-LangChain与Agent.md` |
