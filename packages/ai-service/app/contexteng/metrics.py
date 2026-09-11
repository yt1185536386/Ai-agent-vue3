"""context 维度指标聚合查询(看板数据源)。

线上指标:cx_retrieval_events(零结果率/分数分布/耗时)、
cx_context_snapshots(注入率/token 水位/组成占比);
离线指标:cx_metrics_daily 的 recall_at_k / precision_at_k(eval 上报)。
"""
from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexteng.models import (
    CxContextSnapshot, CxMetricsDaily, CxRetrievalEvent,
)


def _day_start(days: int) -> datetime:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=days - 1)


def _p95(values: list[float]) -> float:
    """p95(线性插值法的近秩简化版:排序后取 95% 位)"""
    if not values:
        return 0.0
    vs = sorted(values)
    idx = min(len(vs) - 1, int(len(vs) * 0.95 + 0.9999) - 1)
    return vs[max(idx, 0)]


def _histogram(values: list[float], buckets: int = 10) -> list[dict]:
    """0-1 区间等宽直方图(相似度分数分布用)"""
    counts = [0] * buckets
    for v in values:
        i = min(buckets - 1, max(0, int(v * buckets)))
        counts[i] += 1
    return [{"lo": round(i / buckets, 2), "hi": round((i + 1) / buckets, 2),
             "count": counts[i]} for i in range(buckets)]


async def overview(session: AsyncSession, days: int = 30) -> dict:
    """看板聚合:命中率、零结果率、分数分布、token 分布、注入率"""
    since = _day_start(days)
    # ---- 检索侧 ----
    r = (await session.execute(
        select(
            func.count().label("n"),
            func.sum(case((CxRetrievalEvent.hit_count == 0, 1), else_=0)).label("zero_n"),
            func.avg(CxRetrievalEvent.max_score).label("avg_max"),
            func.avg(CxRetrievalEvent.hit_count).label("avg_hits"),
            func.avg(CxRetrievalEvent.latency_ms).label("avg_lat"),
        ).where(CxRetrievalEvent.created_at >= since)
    )).one()
    scores = (await session.execute(
        select(CxRetrievalEvent.max_score)
        .where(CxRetrievalEvent.created_at >= since)
    )).scalars().all()
    # 零结果 query 榜 TOP N(回收评测用例的候选)
    zero_top = (await session.execute(
        select(CxRetrievalEvent.query, func.count().label("n"),
               func.avg(CxRetrievalEvent.max_score).label("avg_score"))
        .where(CxRetrievalEvent.created_at >= since,
               CxRetrievalEvent.hit_count == 0)
        .group_by(CxRetrievalEvent.query)
        .order_by(func.count().desc())
        .limit(10)
    )).all()
    # 低分检索事件榜(阈值合理性分析与用例回收候选)
    low_events = (await session.execute(
        select(CxRetrievalEvent)
        .where(CxRetrievalEvent.created_at >= since)
        .order_by(CxRetrievalEvent.max_score.asc())
        .limit(10)
    )).scalars().all()
    # ---- context 快照侧 ----
    s = (await session.execute(
        select(
            func.count().label("n"),
            func.sum(CxContextSnapshot.rag_injected).label("rag_n"),
        ).where(CxContextSnapshot.created_at >= since)
    )).one()
    tokens = [t for t in (await session.execute(
        select(CxContextSnapshot.total_tokens)
        .where(CxContextSnapshot.created_at >= since,
               CxContextSnapshot.total_tokens >= 0)
    )).scalars().all()]
    return {
        "days": days,
        "retrieval_count": r.n,
        "zero_result_rate": round((r.zero_n or 0) / r.n, 4) if r.n else 0.0,
        "avg_max_score": round(r.avg_max or 0, 4),
        "avg_hit_count": round(r.avg_hits or 0, 2),
        "avg_retrieval_latency_ms": round(float(r.avg_lat or 0), 1),
        "score_histogram": _histogram(list(scores)),
        "snapshot_count": s.n,
        "rag_inject_rate": round((s.rag_n or 0) / s.n, 4) if s.n else 0.0,
        "avg_context_tokens": round(sum(tokens) / len(tokens), 1) if tokens else 0.0,
        "p95_context_tokens": int(_p95(tokens)),
        "zero_result_top": [
            {"query": q, "count": n, "avg_max_score": round(sc or 0, 4)}
            for q, n, sc in zero_top
        ],
        "low_score_events": [
            {"id": e.id, "query": e.query, "max_score": round(e.max_score, 4),
             "hit_count": e.hit_count, "created_at": e.created_at.isoformat() if e.created_at else None}
            for e in low_events
        ],
    }


async def trends(session: AsyncSession, days: int = 14) -> dict:
    """趋势序列:按天聚合检索/快照指标 + 离线评测(recall/precision)"""
    since = _day_start(days)
    day_r = func.date(CxRetrievalEvent.created_at)
    r_rows = (await session.execute(
        select(
            day_r.label("d"),
            func.count().label("n"),
            func.sum(case((CxRetrievalEvent.hit_count == 0, 1), else_=0)).label("zero_n"),
            func.avg(CxRetrievalEvent.max_score).label("avg_max"),
        )
        .where(CxRetrievalEvent.created_at >= since)
        .group_by(day_r)
    )).all()
    day_s = func.date(CxContextSnapshot.created_at)
    s_rows = (await session.execute(
        select(
            day_s.label("d"),
            func.count().label("n"),
            func.sum(CxContextSnapshot.rag_injected).label("rag_n"),
            func.avg(case((CxContextSnapshot.total_tokens >= 0,
                           CxContextSnapshot.total_tokens))).label("avg_tokens"),
            func.avg(CxContextSnapshot.system_tokens).label("avg_system"),
            func.avg(CxContextSnapshot.history_tokens).label("avg_history"),
            func.avg(CxContextSnapshot.tool_tokens).label("avg_tool"),
        )
        .where(CxContextSnapshot.created_at >= since)
        .group_by(day_s)
    )).all()
    # 每日 token p95(数据量小,取明细在 Python 侧算)
    token_rows = (await session.execute(
        select(day_s.label("d"), CxContextSnapshot.total_tokens)
        .where(CxContextSnapshot.created_at >= since,
               CxContextSnapshot.total_tokens >= 0)
    )).all()
    tokens_by_day: dict[str, list[float]] = {}
    for d, t in token_rows:
        tokens_by_day.setdefault(str(d), []).append(t)
    # 离线评测指标(每日最近一次,eval 上报写入)
    e_rows = (await session.execute(
        select(CxMetricsDaily.stat_date,
               CxMetricsDaily.recall_at_k, CxMetricsDaily.precision_at_k)
        .where(CxMetricsDaily.stat_date >= since.strftime("%Y-%m-%d"))
    )).all()
    by_day: dict[str, dict] = {}
    for d, n, zero_n, avg_max in r_rows:
        by_day.setdefault(str(d), {}).update({
            "retrieval_count": n,
            "zero_result_rate": round((zero_n or 0) / n, 4) if n else 0.0,
            "avg_max_score": round(float(avg_max or 0), 4),
        })
    for d, n, rag_n, avg_tokens, avg_sys, avg_his, avg_tool in s_rows:
        by_day.setdefault(str(d), {}).update({
            "snapshot_count": n,
            "rag_inject_rate": round((rag_n or 0) / n, 4) if n else 0.0,
            "avg_context_tokens": round(float(avg_tokens or 0), 1),
            "p95_context_tokens": int(_p95(tokens_by_day.get(str(d), []))),
            "avg_system_tokens": round(float(avg_sys or 0), 1),
            "avg_history_tokens": round(float(avg_his or 0), 1),
            "avg_tool_tokens": round(float(avg_tool or 0), 1),
        })
    for d, recall, precision in e_rows:
        by_day.setdefault(str(d), {}).update({
            "recall_at_k": recall, "precision_at_k": precision,
        })
    series = [{"date": d, **vals} for d, vals in sorted(by_day.items())]
    return {"days": days, "series": series}
