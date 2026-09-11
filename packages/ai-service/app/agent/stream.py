"""流式/非流式运行器:把 ReAct 图的执行暴露为自定义 SSE 事件流。

事件:token / reasoning / tool_start / tool_end / approval_request / done / error。

卡片事件解耦:业务工具(如 query_my_assets/query_users/query_options)
的结构化结果需要推给前端渲染交互卡片——这部分业务知识不进 harness,
由业务模块通过 register_card_hook(tool_name, hook) 注册;
hook 接收工具结果字符串,返回 (事件名, data) 或 None。
"""
import json
import uuid
from typing import AsyncIterator, Callable

# 工具名 → 卡片钩子:result_str → (event_type, data) | None
_CARD_HOOKS: dict[str, Callable[[str], tuple[str, dict] | None]] = {}


def register_card_hook(tool_name: str, hook: Callable[[str], tuple[str, dict] | None]) -> None:
    """登记某个工具结果的卡片事件转换钩子"""
    _CARD_HOOKS[tool_name] = hook


def sse_event(event_type: str, data: dict) -> bytes:
    """构造一行 SSE 事件(event: + data:)"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n".encode()


async def run_agent_non_stream(agent, messages: list, model: str,
                               config: dict | None = None) -> dict:
    """非流式:跑完整个 ReAct 循环,返回最终回答(同时带上 reasoning_content)"""
    from app.agent.messages import completion_payload, mark_content_format

    result = await agent.ainvoke({"messages": messages}, config=config)
    # HITL:非流式路径撞上 interrupt 时,提示改用流式审批(断点已存,可恢复)
    interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
    if interrupts:
        details = "、".join(str(i.value.get("detail", i.value)) for i in interrupts)
        payload = completion_payload(
            model, f"操作已暂停等待人工审批:{details}。请在对话界面完成审批。")
        return mark_content_format(payload)
    final = result["messages"][-1]
    answer = final.content
    if not isinstance(answer, str):
        answer = "".join(p.get("text", "") for p in answer if isinstance(p, dict))
    payload = completion_payload(model, answer)
    # 把思考内容放在 assistant message 的 additional_kwargs 里,前端 LangChain 旧路径可见
    if hasattr(final, "additional_kwargs") and final.additional_kwargs.get("reasoning_content"):
        payload["choices"][0]["message"]["reasoning_content"] = final.additional_kwargs["reasoning_content"]
    return mark_content_format(payload)


async def run_agent_stream(agent, graph_input, model: str,
                           config: dict | None = None,
                           collector: dict | None = None) -> AsyncIterator[bytes]:
    """流式:对外暴露自定义 SSE 事件流,前端剥离 LangChain 后直接消费。

    graph_input:首轮为 {"messages": [...]},HITL 恢复时为 Command(resume=决策);
    config: 带 thread_id 的 LangGraph 配置(checkpointer 按它定位断点);
    collector: 可选,{"text": ""} 容器,累积所有已发给前端的正文 token
      (服务端落库助手消息用——与用户所见逐字一致,断连时手里有半条消息)。
    流结束后若图处于 interrupt 暂停态,补发 approval_request 事件。"""
    cid = f"chatcmpl-{uuid.uuid4().hex[:24]}" # 会话 ID
    # 已经为某个工具发过 tool_start 但还没收到 tool_end 时,后续 token 不应再触发
    in_tool = False      # 工具调用状态标志

    async for event in agent.astream_events(graph_input, config=config, version="v2"): # 流式事件
        kind = event["event"] # 事件类型
        # 子图内部事件过滤(命名空间分隔符 + tags 冗余):
        # astream_events 不过滤子图内部事件——守门子图里分类器的
        # on_chat_model_stream(意图 JSON/reasoning)若不作理会泄漏成正文 token。
        # 实测(langgraph 1.2.9):父图节点内事件 ns 为单段("agent:<task_id>"),
        # 子图内部事件 ns 必含 "|"("guardrail:<id>|classify_decide:<id>"),
        # 故按 "|" 过滤——父图 agent/tools 事件不受影响,
        # 未来任何新子图的内部事件默认不处理,永不泄漏;
        # tags:守门分类调用显式打 guardrail_internal,ns 形态变化时仍兜底
        ns = (event.get("metadata") or {}).get("langgraph_checkpoint_ns") or ""
        if "|" in ns:
            continue
        if "guardrail_internal" in (event.get("tags") or []):
            continue
        if kind == "on_chat_model_stream": # 模型输出
            chunk = event["data"]["chunk"]  # 模型输出 chunk
            content = chunk.content  # 模型输出内容
            # 3.3 思考过程流式透传:思考型模型(qwen3/deepseek/k3)把推理放在
            # additional_kwargs.reasoning_content;它就是现代版 ReAct 里的 Thought。
            # 必须在 tool_calls 判断之前提取——工具决策帧里也可能带思考 token。
            reasoning = getattr(chunk, "additional_kwargs", {}).get("reasoning_content")  # 思考内容
            if reasoning:  # 有思考内容
                yield sse_event("reasoning", {"content": reasoning})  # 发送思考事件
            tool_calls = getattr(chunk, "tool_call_chunks", None) or getattr(chunk, "tool_calls", None)  # 工具调用信息
            # 工具调用开始(OpenAI 兼容:chunk.tool_call_chunks 含 name/args)
            if tool_calls and not in_tool:  # 有工具调用信息且未调用工具
                tc = tool_calls[0] if isinstance(tool_calls, list) else None  # 第一个工具调用信息
                name = (tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)) or "tool"  # 工具名
                args = (tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", None)) or {}  # 工具参数
                if isinstance(args, str):  # 工具参数是字符串
                    try: args = json.loads(args) if args else {}  # 解析 JSON 字符串
                    except: args = {"raw": args}  # 解析失败,保留原始字符串
                in_tool = True  # 标记为调用工具状态
                yield sse_event("tool_start", {"name": name, "args": args})  # 发送工具调用事件
                continue  # 工具决策帧不输出 token
            # 工具进行中忽略文本 token(避免打扰),但模型可能给一些"我先去查"之类的话
            # 实际 LangGraph 会等工具结束后再生成最终回答,所以这里直接丢弃
            if in_tool:  # 工具调用中,忽略文本 token
                continue  # 跳过文本 token
            if isinstance(content, str) and content:  # 有文本内容
                if collector is not None:
                    collector["text"] += content  # 落库收集:与用户所见逐字一致
                yield sse_event("token", {"content": content})  # 发送文本 token
        elif kind == "on_tool_end":  # 工具调用结束
            in_tool = False  # 标记为未调用工具状态
            output = event["data"].get("output")  # 工具输出
            tool_name = (event.get("name") or "").split(":")[-1]  # 工具名
            if hasattr(output, "content"):
                result = output.content  # 工具输出内容
            elif isinstance(output, str):  # 工具输出是字符串
                result = output  # 工具输出内容 
            else:
                try:
                    result = json.dumps(output, ensure_ascii=False, default=str)  # 工具输出内容 JSON 字符串
                except Exception:
                    result = str(output)  # 工具输出内容 字符串
            yield sse_event("tool_end", {"name": tool_name, "result": result})  # 发送工具调用结束事件
            # 业务卡片钩子:工具结果 → 前端交互卡片事件(由业务模块注册)
            hook = _CARD_HOOKS.get(tool_name)
            if hook:
                try:
                    card = hook(result)
                except Exception:
                    card = None
                if card:
                    yield sse_event(card[0], card[1])

    if config:
        state = await agent.aget_state(config)
        # 守门拒绝:图在入口子图内终结,全程无模型 token 流出——
        # 把子图写进状态的拒绝文案补发为 token(一次性,文案短;
        # 形状与正常 token 流一致,前端零改动,collector 同管道累积落库)。
        # verdict 每轮被子图覆盖写,refuse ⟺ 本轮被拒(resume 轮不会被拒:
        # 拒则图已终结无断点,谈不上恢复)
        if (state.values or {}).get("verdict") == "refuse":
            msgs = state.values.get("messages") or []
            refusal = ""
            if msgs:
                c = getattr(msgs[-1], "content", "")
                refusal = c if isinstance(c, str) else "".join(
                    p.get("text", "") for p in c if isinstance(p, dict))
            if refusal:
                if collector is not None:
                    collector["text"] += refusal
                yield sse_event("token", {"content": refusal})
        # HITL:流结束时图可能正挂在 interrupt 上等审批——把待审批明细发给前端
        pending = [
            {"id": intr.id, "value": intr.value}
            for task in (state.tasks or [])
            for intr in (task.interrupts or [])
        ]
        if pending:
            yield sse_event("approval_request", {"items": pending})  # 发送待审批明细事件

    yield sse_event("done", {"id": cid})  # 发送完成事件
    yield b"data: [DONE]\n\n"
