"""prompt 维度指标聚合查询(看板数据源)。

线上指标来自 pe_usage_events(调用量/token/耗时,按版本归因);
离线指标(回归通过率)来自 pe_metrics_daily 的 eval 上报行。
"""
from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.prompteng.models import PeMetricsDaily, PeTemplate, PeUsageEvent


def _day_start(days: int) -> datetime:
    """本地时区今天 0 点往前推 days-1 天(含今天)"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=days - 1)


async def overview(session: AsyncSession, days: int = 30) -> dict:
    """看板聚合:各模板调用量、版本分布、token、通过率、沉默模板"""
    since = _day_start(days)
    # 按 模板 × 版本 聚合(pe_usage_events;version=0 表示代码默认)
    known_tokens = case((PeUsageEvent.prompt_tokens >= 0, PeUsageEvent.prompt_tokens))
    n_known = func.sum(case((PeUsageEvent.prompt_tokens >= 0, 1), else_=0))
    rows = (await session.execute(
        select(
            PeUsageEvent.template_key,
            PeUsageEvent.version,
            func.count().label("call_count"),
            func.sum(known_tokens).label("token_sum"),
            n_known.label("token_n"),
            func.avg(PeUsageEvent.latency_ms).label("avg_latency"),
        )
        .where(PeUsageEvent.created_at >= since)
        .group_by(PeUsageEvent.template_key, PeUsageEvent.version)
    )).all()
    by_template: dict[str, dict] = {}
    for key, version, cnt, token_sum, token_n, avg_lat in rows:
        t = by_template.setdefault(key, {
            "template_key": key, "call_count": 0,
            "token_sum": 0, "token_n": 0, "lat_sum": 0.0,
            "versions": [], "eval_pass_rate": None,
        })
        t["call_count"] += cnt
        t["token_sum"] += token_sum or 0
        t["token_n"] += token_n or 0
        t["lat_sum"] += float(avg_lat or 0) * cnt
        t["versions"].append({"version": version, "call_count": cnt})
    # 最近一次回归通过率(按模板,来自 eval 上报的合计行 version=0)
    rate_rows = (await session.execute(
        select(PeMetricsDaily.template_key,
               func.max(PeMetricsDaily.stat_date).label("d"))
        .where(PeMetricsDaily.eval_pass_rate.isnot(None),
               PeMetricsDaily.version == 0)
        .group_by(PeMetricsDaily.template_key)
    )).all()
    for key, d in rate_rows:
        rate = (await session.execute(
            select(PeMetricsDaily.eval_pass_rate).where(
                PeMetricsDaily.template_key == key,
                PeMetricsDaily.stat_date == d,
                PeMetricsDaily.version == 0)
        )).scalar_one_or_none()
        if key in by_template:
            by_template[key]["eval_pass_rate"] = rate
    templates = []
    for t in by_template.values():
        templates.append({
            "template_key": t["template_key"],
            "call_count": t["call_count"],
            "avg_prompt_tokens": round(t["token_sum"] / t["token_n"], 1) if t["token_n"] else None,
            "avg_latency_ms": round(t["lat_sum"] / t["call_count"], 1) if t["call_count"] else 0,
            "versions": sorted(t["versions"], key=lambda v: v["version"]),
            "eval_pass_rate": t["eval_pass_rate"],
        })
    # 沉默模板:近 7 天零调用的 active 模板
    week = _day_start(7)
    active_keys = set((await session.execute(
        select(PeTemplate.key).where(PeTemplate.status == "active"))).scalars().all())
    called_keys = set((await session.execute(
        select(PeUsageEvent.template_key).where(PeUsageEvent.created_at >= week)
        .group_by(PeUsageEvent.template_key))).scalars().all())
    silent = sorted(active_keys - called_keys)
    return {
        "days": days,
        "total_calls": sum(t["call_count"] for t in templates),
        "active_templates": len(active_keys),
        "silent_templates": silent,
        "templates": templates,
    }


async def template_trend(session: AsyncSession, key: str, days: int = 14) -> dict:
    """单模板趋势:按天 × 按版本(调用量 / prompt token 均值 / 耗时)"""
    since = _day_start(days)
    day = func.date(PeUsageEvent.created_at)
    known_tokens = case((PeUsageEvent.prompt_tokens >= 0, PeUsageEvent.prompt_tokens))
    n_known = func.sum(case((PeUsageEvent.prompt_tokens >= 0, 1), else_=0))
    rows = (await session.execute(
        select(
            day.label("d"),
            PeUsageEvent.version,
            func.count().label("call_count"),
            func.sum(known_tokens).label("token_sum"),
            n_known.label("token_n"),
            func.avg(PeUsageEvent.latency_ms).label("avg_latency"),
        )
        .where(PeUsageEvent.template_key == key,
               PeUsageEvent.created_at >= since)
        .group_by(day, PeUsageEvent.version)
        .order_by(day)
    )).all()
    points = [{
        "date": str(d), "version": v, "call_count": c,
        "avg_prompt_tokens": round(ts / tn, 1) if tn else None,
        "avg_latency_ms": round(float(lat or 0), 1),
    } for d, v, c, ts, tn, lat in rows]
    return {"template_key": key, "days": days, "points": points}
