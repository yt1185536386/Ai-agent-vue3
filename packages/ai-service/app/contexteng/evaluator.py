"""检索离线评测(in-process)与日聚合写库。

run_retrieval_eval:直接调 app.rag.search_chunks(与线上同一实现),
对 cx_eval_cases(enabled)计算 Recall@K / Precision@K / 零结果率,
结果 upsert 到 cx_metrics_daily ——「离线指标上板」。

eval 包(packages/eval)的 run_retrieval 复用本模块,保证
离线评测与线上检索行为一致、结果口径一致。
"""
import json
import uuid
from datetime import datetime

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexteng.models import (
    CxContextSnapshot, CxEvalCase, CxMetricsDaily, CxRetrievalEvent,
)
from app.rag.engine import embed_texts, search_chunks


def _score_case(case: dict, hits: list[dict], k: int) -> dict:
    """单用例打分:recall = 命中期望文档占比;precision = 命中里相关占比"""
    expect_docs = set(json.loads(case["expect_doc_ids"] or "[]"))
    expect_contains = json.loads(case["expect_contains"] or "[]")
    hit_docs = [h["doc_id"] for h in hits]
    hit_docs_set = set(hit_docs)
    recall = (len(expect_docs & hit_docs_set) / len(expect_docs)) if expect_docs else None
    precision = (len([d for d in hit_docs if d in expect_docs]) / len(hit_docs)) if hit_docs else 0.0
    text_blob = "\n".join(h.get("text", "") for h in hits)
    contains_ok = all(p in text_blob for p in expect_contains) if expect_contains else None
    return {
        "recall": recall, "precision": precision,
        "contains_ok": contains_ok, "hit_count": len(hits),
    }


async def run_retrieval_eval(
    session: AsyncSession,
    user_id: str,
    provider: dict,
    embed_model: str,
    *,
    top_k: int | None = None,
    threshold: float | None = None,
) -> dict:
    """对全部 enabled 用例跑一遍检索评测,返回汇总指标(不写库,由调用方决定)。

    top_k/threshold 缺省用当前策略;eval 包 --strategy 对比时显式传入。
    """
    from app.contexteng import strategy as cx_strategy
    cfg = cx_strategy.current()
    k = top_k if top_k is not None else cfg["top_k"]
    th = threshold if threshold is not None else cfg["threshold"]

    cases = (await session.execute(
        select(CxEvalCase).where(CxEvalCase.status == "enabled")
    )).scalars().all()
    details = []
    for c in cases:
        case = {"id": c.id, "query": c.query,
                "expect_doc_ids": c.expect_doc_ids,
                "expect_contains": c.expect_contains}
        try:
            embs = await embed_texts(provider, embed_model, [c.query])
            hits = await search_chunks(session, user_id, embs[0], top_k=k)
            hits = [h for h in hits if h.get("score", 0) > th]
            details.append({**case, **_score_case(case, hits, k)})
        except Exception as e:
            details.append({**case, "error": str(e), "recall": None,
                            "precision": 0.0, "hit_count": 0})
    n = len(details)
    recalls = [d["recall"] for d in details if d.get("recall") is not None]
    precisions = [d["precision"] for d in details if d.get("recall") is not None or d.get("error") is None]
    zero_n = sum(1 for d in details if d.get("hit_count", 0) == 0)
    return {
        "case_count": n,
        "top_k": k,
        "threshold": th,
        "recall_at_k": round(sum(recalls) / len(recalls), 4) if recalls else None,
        "precision_at_k": round(sum(precisions) / len(precisions), 4) if precisions else None,
        "zero_result_rate": round(zero_n / n, 4) if n else None,
        "details": details,
    }


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


async def upsert_cx_daily(
    session: AsyncSession, stat_date: str | None = None, *,
    recall_at_k: float | None = None, precision_at_k: float | None = None,
) -> dict:
    """upsert cx_metrics_daily 一行:在线指标惰性聚合 + 离线指标(给定时)写入"""
    d = stat_date or _today()
    day_start = datetime.strptime(d, "%Y-%m-%d")
    day_end = day_start.replace(hour=23, minute=59, second=59)
    r = (await session.execute(
        select(
            func.count().label("n"),
            func.sum(case((CxRetrievalEvent.hit_count == 0, 1), else_=0)).label("zero_n"),
            func.avg(CxRetrievalEvent.max_score).label("avg_max"),
            func.avg(CxRetrievalEvent.hit_count).label("avg_hits"),
        ).where(CxRetrievalEvent.created_at >= day_start,
                CxRetrievalEvent.created_at <= day_end)
    )).one()
    s = (await session.execute(
        select(
            func.count().label("n"),
            func.sum(CxContextSnapshot.rag_injected).label("rag_n"),
            func.avg(case((CxContextSnapshot.total_tokens >= 0,
                                CxContextSnapshot.total_tokens))).label("avg_tokens"),
        ).where(CxContextSnapshot.created_at >= day_start,
                CxContextSnapshot.created_at <= day_end)
    )).one()
    tokens = [t for t in (await session.execute(
        select(CxContextSnapshot.total_tokens).where(
            CxContextSnapshot.created_at >= day_start,
            CxContextSnapshot.created_at <= day_end,
            CxContextSnapshot.total_tokens >= 0)
    )).scalars().all()]
    tokens.sort()
    p95 = tokens[min(len(tokens) - 1, int(len(tokens) * 0.95 + 0.9999) - 1)] if tokens else 0

    row = (await session.execute(
        select(CxMetricsDaily).where(CxMetricsDaily.stat_date == d)
    )).scalar_one_or_none()
    if not row:
        row = CxMetricsDaily(id=uuid.uuid4().hex, stat_date=d)
        session.add(row)
    row.retrieval_count = r.n
    row.zero_result_rate = round((r.zero_n or 0) / r.n, 4) if r.n else 0.0
    row.avg_max_score = round(r.avg_max or 0, 4)
    row.avg_hit_count = round(r.avg_hits or 0, 2)
    row.rag_inject_rate = round((s.rag_n or 0) / s.n, 4) if s.n else 0.0
    row.avg_context_tokens = round(s.avg_tokens or 0, 1)
    row.p95_context_tokens = int(p95)
    if recall_at_k is not None:
        row.recall_at_k = recall_at_k
    if precision_at_k is not None:
        row.precision_at_k = precision_at_k
    await session.commit()
    return {"stat_date": d, "retrieval_count": row.retrieval_count,
            "recall_at_k": row.recall_at_k, "precision_at_k": row.precision_at_k}


async def upsert_pe_daily_eval(
    session: AsyncSession, template_key: str, pass_rate: float,
    stat_date: str | None = None, version: int | None = None,
) -> dict:
    """regression/quality 评测通过率写入 pe_metrics_daily(按模板当前版本归因,
    同时写 version=0 合计行供看板直查)"""
    from app.prompteng.models import PeMetricsDaily, PeUsageEvent
    from app.prompteng.service import active_version
    d = stat_date or _today()
    ver = version if version is not None else active_version(template_key)
    day_start = datetime.strptime(d, "%Y-%m-%d")
    day_end = day_start.replace(hour=23, minute=59, second=59)
    # 当日调用统计(合计行)
    agg = (await session.execute(
        select(
            func.count().label("n"),
            func.avg(case((PeUsageEvent.prompt_tokens >= 0,
                                PeUsageEvent.prompt_tokens))).label("avg_tokens"),
            func.avg(PeUsageEvent.latency_ms).label("avg_lat"),
        ).where(PeUsageEvent.template_key == template_key,
                PeUsageEvent.created_at >= day_start,
                PeUsageEvent.created_at <= day_end)
    )).one()
    for v, with_stats in ((0, True), (ver, False)):
        if v != 0 and ver == 0:
            continue  # 无 DB 模板时合计行即版本行,避免重复
        row = (await session.execute(
            select(PeMetricsDaily).where(
                PeMetricsDaily.stat_date == d,
                PeMetricsDaily.template_key == template_key,
                PeMetricsDaily.version == v)
        )).scalar_one_or_none()
        if not row:
            row = PeMetricsDaily(id=uuid.uuid4().hex, stat_date=d,
                                 template_key=template_key, version=v)
            session.add(row)
        row.eval_pass_rate = pass_rate
        if with_stats:
            row.call_count = agg.n
            row.avg_prompt_tokens = round(agg.avg_tokens or 0, 1)
            row.avg_latency_ms = round(agg.avg_lat or 0, 1)
    await session.commit()
    return {"stat_date": d, "template_key": template_key,
            "version": ver, "eval_pass_rate": pass_rate}


async def recycle_zero_result(session: AsyncSession, event_id: str, *,
                              expect_doc_ids: list | None = None,
                              expect_contains: list | None = None) -> dict:
    """从零结果(或低分)检索事件回收为评测用例(source=online)"""
    ev = (await session.execute(
        select(CxRetrievalEvent).where(CxRetrievalEvent.id == event_id)
    )).scalar_one_or_none()
    if not ev:
        raise KeyError(f"检索事件不存在: {event_id}")
    case = CxEvalCase(
        id=uuid.uuid4().hex,
        query=ev.query,
        expect_doc_ids=json.dumps(expect_doc_ids or [], ensure_ascii=False),
        expect_contains=json.dumps(expect_contains or [], ensure_ascii=False),
        source="online", status="enabled",
    )
    session.add(case)
    await session.commit()
    return {"id": case.id, "query": case.query, "source": case.source}


async def delete_eval_cases_by_event(session: AsyncSession, event_id: str) -> int:
    """清理某事件回收出的用例(暂未暴露 API,预留)"""
    res = await session.execute(
        delete(CxEvalCase).where(CxEvalCase.id == event_id))
    await session.commit()
    return res.rowcount or 0
