"""钩子实现:检索事件 / context 快照 / prompt 使用事件的异步落库。

钩子纪律(全模块遵守):
1. 所有上报入口 try/except 全捕获,观测失败绝不影响主链路;
2. 落库用独立 session(sessionmaker 新建),不与请求 session 混用;
3. 耗时超过 5ms 的部分(全部 DB 写入)放后台任务(asyncio.create_task)。

请求上下文(user_id / conversation_id)由 main.py 在请求入口经
bind_request_context() 绑定到 contextvar,工具/钩子回调内读取,
避免穿透 harness 改函数签名。
"""
import asyncio
import contextvars
import json
import logging
import uuid

from app.contexteng.events import ContextSnapshot, PromptUsageEvent, RetrievalEvent
from app.contexteng.models import CxContextSnapshot, CxRetrievalEvent

log = logging.getLogger(__name__)

# 请求级上下文:{"user_id": ..., "conversation_id": ...(adhoc 为 "")}
_request_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "cx_request_ctx", default={"user_id": "", "conversation_id": ""})


def bind_request_context(user_id: str, conversation_id: str) -> None:
    """请求入口调用:绑定当前请求的用户与会话(供工具/钩子读取)"""
    _request_ctx.set({"user_id": user_id or "", "conversation_id": conversation_id or ""})


def current_context() -> dict:
    return _request_ctx.get()


# 会话最近注入的检索 chunk_id(快照落 rag_chunk_ids 用;进程内弱状态,重启清零)
_recent_rag_chunks: dict[str, list[str]] = {}


def _submit(coro) -> None:
    """把落库协程丢到后台任务;异常只记日志,绝不冒泡到主链路"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # 非异步上下文(如脚本),静默跳过
    task = loop.create_task(coro)
    def _swallow(t: asyncio.Task) -> None:
        if not t.cancelled() and t.exception():
            log.warning("contexteng 后台落库失败(已静默): %s", t.exception())
    task.add_done_callback(_swallow)


# ---------- 检索事件 ----------

def report_retrieval(event: RetrievalEvent) -> None:
    """search_docs 调用后上报(同步入口,异步落库)"""
    try:
        ctx = current_context()
        event.setdefault("user_id", ctx["user_id"])
        event.setdefault("conversation_id", ctx["conversation_id"])
        chunk_ids = [h.get("chunk_id", "") for h in event.get("hits", []) if h.get("chunk_id")]
        if event.get("conversation_id"):
            _recent_rag_chunks[event["conversation_id"]] = chunk_ids
        _submit(_insert_retrieval(dict(event)))
    except Exception:
        pass  # 观测失败绝不影响主链路


async def _insert_retrieval(event: dict) -> None:
    from app.core.db import sessionmaker
    async with sessionmaker()() as s:
        s.add(CxRetrievalEvent(
            id=uuid.uuid4().hex,
            user_id=event.get("user_id", ""),
            conversation_id=event.get("conversation_id", ""),
            query=event.get("query", ""),
            strategy=event.get("strategy", ""),
            top_k=event.get("top_k", 0),
            threshold=event.get("threshold", 0.0),
            hits=json.dumps(event.get("hits", []), ensure_ascii=False),
            hit_count=event.get("hit_count", 0),
            max_score=event.get("max_score", 0.0),
            latency_ms=event.get("latency_ms", 0),
        ))
        await s.commit()


# ---------- Context 快照(+ 派生 prompt 使用事件) ----------

def report_model_call(snapshot: ContextSnapshot) -> None:
    """loop.py 模型调用后上报:写 cx_context_snapshots,并派生 pe_usage_events"""
    try:
        ctx = current_context()
        snapshot.setdefault("user_id", ctx["user_id"])
        snapshot.setdefault("conversation_id", ctx["conversation_id"])
        conv_id = snapshot.get("conversation_id", "")
        snapshot["rag_chunk_ids"] = _recent_rag_chunks.get(conv_id, [])
        _submit(_insert_snapshot(dict(snapshot)))
    except Exception:
        pass


async def _insert_snapshot(snap: dict) -> None:
    from app.core.db import sessionmaker
    from app.prompteng.models import PeUsageEvent
    from app.prompteng.service import active_version
    async with sessionmaker()() as s:
        s.add(CxContextSnapshot(
            id=uuid.uuid4().hex,
            conversation_id=snap.get("conversation_id", ""),
            user_id=snap.get("user_id", ""),
            model=snap.get("model", ""),
            total_tokens=snap.get("total_tokens", -1),
            system_tokens=snap.get("system_tokens", 0),
            history_tokens=snap.get("history_tokens", 0),
            tool_tokens=snap.get("tool_tokens", 0),
            message_count=snap.get("message_count", 0),
            rag_chunk_ids=json.dumps(snap.get("rag_chunk_ids", []), ensure_ascii=False),
            rag_injected=snap.get("rag_injected", 0),
            truncated=snap.get("truncated", 0),
        ))
        # 派生 prompt 使用事件:同一模型调用,按 'agent.system' 模板归因
        s.add(PeUsageEvent(
            id=uuid.uuid4().hex,
            template_key="agent.system",
            version=active_version("agent.system"),
            conversation_id=snap.get("conversation_id", ""),
            user_id=snap.get("user_id", ""),
            prompt_tokens=snap.get("total_tokens", -1),
            latency_ms=snap.get("latency_ms", 0),
        ))
        await s.commit()
