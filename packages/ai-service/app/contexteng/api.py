"""/v1/cx/* 路由:检索事件 / context 快照查询、context 维度指标、
评测用例管理、离线评测触发与结果上报、检索策略管理。

鉴权:require_admin_user(管理台经 vite 代理直连;细粒度权限码 ctx:view
在 NestJS 侧校验)。
"""
import json
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexteng import evaluator, metrics
from app.contexteng import strategy as cx_strategy
from app.contexteng.models import CxContextSnapshot, CxEvalCase, CxRetrievalEvent
from app.core.db import get_session
from app.core.deps import require_admin_user

router = APIRouter(
    prefix="/v1/cx", tags=["contexteng"],
    dependencies=[Depends(require_admin_user)],
)


# ---------- 检索事件 ----------

def _serialize_event(e: CxRetrievalEvent, *, with_hits: bool = False) -> dict:
    out = {
        "id": e.id, "user_id": e.user_id, "conversation_id": e.conversation_id,
        "query": e.query, "strategy": e.strategy, "top_k": e.top_k,
        "threshold": e.threshold, "hit_count": e.hit_count,
        "max_score": e.max_score, "latency_ms": e.latency_ms,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }
    if with_hits:
        out["hits"] = json.loads(e.hits or "[]")
    return out


@router.get("/retrieval/events")
async def list_retrieval_events(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user_id: str | None = Query(default=None),
    zero_result: int | None = Query(default=None, description="1 只看零结果 / 0 只看有结果"),
    strategy: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """检索事件分页查询(时间/用户/零结果过滤)"""
    stmt = select(CxRetrievalEvent)
    count_stmt = select(func.count(CxRetrievalEvent.id))
    conds = []
    if user_id:
        conds.append(CxRetrievalEvent.user_id == user_id)
    if zero_result is not None:
        conds.append(CxRetrievalEvent.hit_count == 0 if zero_result
                     else CxRetrievalEvent.hit_count > 0)
    if strategy:
        conds.append(CxRetrievalEvent.strategy == strategy)
    for c in conds:
        stmt = stmt.where(c)
        count_stmt = count_stmt.where(c)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(
        stmt.order_by(CxRetrievalEvent.created_at.desc())
        .offset((page - 1) * size).limit(size)
    )).scalars().all()
    return {"total": total, "page": page, "size": size,
            "events": [_serialize_event(e) for e in rows]}


@router.get("/retrieval/events/{event_id}")
async def get_retrieval_event(event_id: str, session: AsyncSession = Depends(get_session)):
    """事件详情(命中 chunk 展开)"""
    e = (await session.execute(
        select(CxRetrievalEvent).where(CxRetrievalEvent.id == event_id))
    ).scalar_one_or_none()
    if not e:
        raise HTTPException(404, "检索事件不存在")
    return _serialize_event(e, with_hits=True)


# ---------- Context 快照 ----------

def _serialize_snapshot(s: CxContextSnapshot) -> dict:
    return {
        "id": s.id, "conversation_id": s.conversation_id, "user_id": s.user_id,
        "model": s.model, "total_tokens": s.total_tokens,
        "system_tokens": s.system_tokens, "history_tokens": s.history_tokens,
        "tool_tokens": s.tool_tokens, "message_count": s.message_count,
        "rag_chunk_ids": json.loads(s.rag_chunk_ids or "[]"),
        "rag_injected": s.rag_injected, "truncated": s.truncated,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/snapshots")
async def list_snapshots(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    conversation_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    rag_injected: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """context 快照分页查询"""
    stmt = select(CxContextSnapshot)
    count_stmt = select(func.count(CxContextSnapshot.id))
    conds = []
    if conversation_id:
        conds.append(CxContextSnapshot.conversation_id == conversation_id)
    if user_id:
        conds.append(CxContextSnapshot.user_id == user_id)
    if rag_injected is not None:
        conds.append(CxContextSnapshot.rag_injected == rag_injected)
    for c in conds:
        stmt = stmt.where(c)
        count_stmt = count_stmt.where(c)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(
        stmt.order_by(CxContextSnapshot.created_at.desc())
        .offset((page - 1) * size).limit(size)
    )).scalars().all()
    return {"total": total, "page": page, "size": size,
            "snapshots": [_serialize_snapshot(s) for s in rows]}


# ---------- 指标 ----------

@router.get("/metrics/overview")
async def metrics_overview(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
):
    """看板聚合:命中率、分数分布、token 分布"""
    return await metrics.overview(session, days)


@router.get("/metrics/trends")
async def metrics_trends(
    days: int = Query(default=14, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
):
    """趋势序列(按天,含 recall/precision)"""
    return await metrics.trends(session, days)


@router.post("/metrics/report")
async def report_metrics(body: dict, session: AsyncSession = Depends(get_session)):
    """离线评测结果上报(「离线指标上板」):
    kind=retrieval → 写 cx_metrics_daily 的 recall_at_k / precision_at_k;
    kind=prompt    → 写 pe_metrics_daily 的 eval_pass_rate(按模板当前版本归因)。
    """
    kind = body.get("kind", "retrieval")
    stat_date = body.get("stat_date")
    if kind == "retrieval":
        return await evaluator.upsert_cx_daily(
            session, stat_date,
            recall_at_k=body.get("recall_at_k"),
            precision_at_k=body.get("precision_at_k"))
    if kind == "prompt":
        if body.get("eval_pass_rate") is None:
            raise HTTPException(400, "缺少 eval_pass_rate")
        return await evaluator.upsert_pe_daily_eval(
            session,
            body.get("template_key") or "agent.system",
            float(body["eval_pass_rate"]),
            stat_date=stat_date,
            version=body.get("version"))
    raise HTTPException(400, f"未知 kind: {kind}")


# ---------- 评测用例 ----------

def _serialize_case(c: CxEvalCase) -> dict:
    return {
        "id": c.id, "query": c.query,
        "expect_doc_ids": json.loads(c.expect_doc_ids or "[]"),
        "expect_contains": json.loads(c.expect_contains or "[]"),
        "source": c.source, "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/eval-cases")
async def list_eval_cases(
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """评测用例列表"""
    stmt = select(CxEvalCase).order_by(CxEvalCase.created_at.desc())
    if status:
        stmt = stmt.where(CxEvalCase.status == status)
    if source:
        stmt = stmt.where(CxEvalCase.source == source)
    rows = (await session.execute(stmt)).scalars().all()
    return {"cases": [_serialize_case(c) for c in rows]}


@router.post("/eval-cases", status_code=201)
async def create_eval_case(body: dict, session: AsyncSession = Depends(get_session)):
    """新增评测用例(人工标注)"""
    query = (body.get("query") or "").strip()
    if not query:
        raise HTTPException(400, "query 不能为空")
    case = CxEvalCase(
        id=uuid.uuid4().hex, query=query,
        expect_doc_ids=json.dumps(body.get("expect_doc_ids") or [], ensure_ascii=False),
        expect_contains=json.dumps(body.get("expect_contains") or [], ensure_ascii=False),
        source="manual", status="enabled",
    )
    session.add(case)
    await session.commit()
    return _serialize_case(case)


@router.post("/eval-cases/{case_id}/status")
async def set_eval_case_status(case_id: str, body: dict,
                               session: AsyncSession = Depends(get_session)):
    """启用/停用用例"""
    case = (await session.execute(
        select(CxEvalCase).where(CxEvalCase.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(404, "用例不存在")
    status = body.get("status")
    if status not in ("enabled", "disabled"):
        raise HTTPException(400, "status 仅支持 enabled / disabled")
    case.status = status
    await session.commit()
    return _serialize_case(case)


@router.post("/eval-cases/recycle", status_code=201)
async def recycle_eval_case(body: dict, session: AsyncSession = Depends(get_session)):
    """从零结果/低分检索事件回收为评测用例(source=online)"""
    try:
        return await evaluator.recycle_zero_result(
            session, body.get("event_id") or "",
            expect_doc_ids=body.get("expect_doc_ids"),
            expect_contains=body.get("expect_contains"))
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.post("/eval/run")
async def run_eval(body: dict | None = None,
                   user_id: str = Depends(require_admin_user),
                   session: AsyncSession = Depends(get_session)):
    """触发离线 retrieval 评测(in-process 调 search_chunks),
    结果写 cx_metrics_daily 的 recall_at_k / precision_at_k"""
    from app.main import PROVIDERS  # 延迟 import 避免循环
    body = body or {}
    provider = PROVIDERS.get(os.getenv("EMBED_PROVIDER", "bailian"))
    if not provider:
        raise HTTPException(500, "未配置嵌入模型来源")
    provider = {**provider, "user_id": user_id}
    embed_model = os.getenv("EMBED_MODEL", "text-embedding-v3")
    result = await evaluator.run_retrieval_eval(
        session, body.get("user_id") or user_id, provider, embed_model,
        top_k=body.get("top_k"), threshold=body.get("threshold"))
    daily = await evaluator.upsert_cx_daily(
        session, recall_at_k=result["recall_at_k"],
        precision_at_k=result["precision_at_k"])
    return {**result, "daily": daily}


# ---------- 检索策略 ----------

@router.get("/strategy")
async def get_strategy():
    """当前检索策略(切分/相似度参数)"""
    return cx_strategy.current()


@router.post("/strategy")
async def update_strategy(body: dict):
    """调整检索策略(立即生效;后续检索事件按新 strategy 标识分组,
    与历史策略指标可分板对比。已入库 chunk 需 /v1/documents/rebuild 重切)"""
    return cx_strategy.update(
        strategy=body.get("strategy"),
        size=body.get("size"), overlap=body.get("overlap"),
        top_k=body.get("top_k"), threshold=body.get("threshold"))
