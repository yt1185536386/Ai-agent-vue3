"""ReAct 循环(harness 核心):手写 LangGraph 图,与 create_react_agent 行为等价。

图结构(无守门时):
              ┌──────────────────────────────┐
              ▼                              │
  START → agent 节点(模型决策) → 条件边:有 tool_calls? → tools 节点(执行工具)
                  │                              │
                  ▼ 无 tool_calls                └─ 回到 agent 节点
                 END

带守门子图时(guardrail 参数,编译好的子图,如 app/guardrail.py):
  START → guardrail ──verdict=="refuse"──→ END
                └──verdict=="pass"──→ agent ⇄ tools → END

HITL(人机回环):写操作工具内部调用 langgraph interrupt() 暂停图,
状态由 SqliteSaver 落盘(ai-service/checkpoints.db,uvicorn 重启不丢),
前端批准/拒绝后携带 Command(resume=决策) 从断点恢复执行
(resume 从断点继续,不重走入口——审批恢复天然跳过守门子图)。

三个关键机制:
1. MessagesState 的 messages 带 reducer(累加):节点只需返回增量 {"messages": [新消息]},
   LangGraph 自动 append 到历史,而不是整体覆盖——这就是"状态流转"的本质。
2. bind_tools 把工具 schema 挂到模型上,模型输出的 tool_calls 字段成为路由依据。
3. ToolNode 负责执行 tool_calls 并把结果包成 ToolMessage 追加回状态。
"""
import os
import time

import aiosqlite
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.prompts import agent_system_prompt

_CHECKPOINT_DB = os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints.db")
_checkpointer: AsyncSqliteSaver | None = None

# ---- 可选注入点(裸钩子,默认 None;harness 不 import 业务模块)----
# context 快照观测器: (snapshot: dict) -> None,模型调用完成后回调;
# 事件结构见 contexteng.events.ContextSnapshot,agent.py 启动时注入 collector
_CONTEXT_OBSERVER = None


def set_context_observer(fn) -> None:
    """注入 context 快照观测器;None 关闭观测"""
    global _CONTEXT_OBSERVER
    _CONTEXT_OBSERVER = fn


def _est_tokens(text: str) -> int:
    """中英混合 token 估算:len(text)/1.6(第一阶段经验系数,
    接真实 tokenizer 后替换;落库字段 comment 已注明"估算值")"""
    return int(len(text) / 1.6)


def _message_text(m) -> str:
    if isinstance(m.content, str):
        return m.content
    return "".join(b.get("text", "") for b in m.content if isinstance(b, dict))


def _build_snapshot(msgs: list, resp, *, model: str, latency_ms: int) -> dict:
    """从消息构成 + usage 构建 context 快照(纯函数,无 IO)。
    三段 token 按消息 role 归类估算;total_tokens 以模型 usage 为准。"""
    system_tokens = history_tokens = tool_tokens = 0
    rag_injected = 0
    for m in msgs:
        tokens = _est_tokens(_message_text(m))
        if m.type == "system":
            system_tokens += tokens
        elif m.type == "tool":
            tool_tokens += tokens
            if getattr(m, "name", "") == "search_docs":
                rag_injected = 1
        else:
            history_tokens += tokens
    usage = getattr(resp, "usage_metadata", None) or {}
    total = usage.get("input_tokens") or usage.get("total_tokens") or -1
    return {
        "model": model,
        "total_tokens": total,
        "system_tokens": system_tokens,
        "history_tokens": history_tokens,
        "tool_tokens": tool_tokens,
        "message_count": len(msgs),
        "rag_injected": rag_injected,
        "truncated": 0,  # 干预能力(第二阶段)上线前恒 0
        "latency_ms": latency_ms,
    }


async def get_checkpointer() -> AsyncSqliteSaver:
    """全局唯一的 SQLite checkpointer(懒初始化;连接随进程生命周期)"""
    global _checkpointer
    if _checkpointer is None:
        conn = await aiosqlite.connect(_CHECKPOINT_DB)
        _checkpointer = AsyncSqliteSaver(conn)
        await _checkpointer.setup()
    return _checkpointer


def _repair_dangling_tool_calls(msgs: list) -> list:
    """修复悬空 tool_calls(纯函数,不改 checkpoint,只修发给模型的副本)。

    工具节点崩溃(如 embedding 配额耗尽)会把带 tool_calls 的 AIMessage
    残留在 checkpoint 尾部而没有对应 ToolMessage,之后每轮都被上游
    400 拒绝(insufficient tool messages),整个会话废掉。
    这里为缺失应答的 tool_call 补占位 ToolMessage(紧贴其 AIMessage,
    保持 OpenAI 要求的相邻顺序),老会话下一轮即自愈。"""
    out = list(msgs)
    for i, m in enumerate(out):
        tcs = getattr(m, "tool_calls", None) or []
        if not tcs:
            continue
        answered = {t.tool_call_id for t in out[i + 1:] if t.type == "tool"}
        missing = [tc["id"] for tc in tcs if tc.get("id") not in answered]
        if missing:
            out[i + 1:i + 1] = [
                ToolMessage(
                    content="(该工具调用因服务中断未返回结果,请基于已有信息回答或建议用户重试)",
                    tool_call_id=tid,
                )
                for tid in missing
            ]
    return out


def make_agent(chat, tools, checkpointer=None, guardrail=None, state_schema=None):
    """手写 ReAct 循环;想对比 prebuilt 行为时,
    换用 create_react_agent(chat, tools, checkpointer=...) 即可。

    guardrail:可选,编译好的守门子图(必须先 compile 再传入;
    子图不传 checkpointer,运行时继承本图的)。传入时 state_schema
    必须带 verdict 键(如 app.guardrail.GuardrailState);
    不传时图退化为 START → agent(不保留空节点,结构干净)。"""
    chat_with_tools = chat.bind_tools(tools)
    model_name = getattr(chat, "model_name", "") or getattr(chat, "model", "") or ""

    async def agent_node(state: MessagesState): # 模型决策节点
        """模型决策节点:把目前累积的全部消息发给模型,返回模型的回复(增量)。
        系统提示(时间+业务规则)只在调用时前置,不写入图状态。
        调用完成后回调 context 快照观测器(失败静默,绝不影响主链路)。"""
        msgs = [SystemMessage(content=agent_system_prompt()),
                *_repair_dangling_tool_calls(state["messages"])]
        t0 = time.perf_counter()
        resp = await chat_with_tools.ainvoke(msgs) # 异步调用模型
        if _CONTEXT_OBSERVER:
            try:
                _CONTEXT_OBSERVER(_build_snapshot(
                    msgs, resp, model=str(model_name),
                    latency_ms=int((time.perf_counter() - t0) * 1000)))
            except Exception:
                pass  # 观测失败绝不影响主链路
        return {"messages": [resp]} # 返回模型回复(增量)

    def should_continue(state: MessagesState): # 条件边路由函数
        """条件边路由函数:看模型最新一条回复里有没有 tool_calls"""
        last = state["messages"][-1]     # 最新一条回复
        return "tools" if last.tool_calls else END # 返回工具边或结束边

    def guardrail_route(state): # 守门子图出口路由
        """拒绝(verdict=refuse)直接终;放行进入 ReAct 循环"""
        return END if state.get("verdict") == "refuse" else "agent"

    g = StateGraph(state_schema or MessagesState) # 状态图
    g.add_node("agent", agent_node) # 模型决策节点
    g.add_node("tools", ToolNode(tools)) # 工具节点
    if guardrail is not None:
        g.add_node("guardrail", guardrail) # 守门子图(入口)
        g.add_edge(START, "guardrail") # 从 START 到守门子图
        g.add_conditional_edges(
            "guardrail", guardrail_route, {"agent": "agent", END: END}) # 守门路由
    else:
        g.add_edge(START, "agent") # 从 START 到 agent 节点
    # 条件边:should_continue 返回 "tools" → 去 tools 节点;返回 END → 结束
    g.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END}) # 条件边
    g.add_edge("tools", "agent")  # 工具结果回灌给模型,开始下一轮决策
    # 挂 checkpointer:interrupt() 暂停时状态落盘,resume 时从断点恢复
    return g.compile(checkpointer=checkpointer) # 编译图
