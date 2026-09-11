"""评测报告:控制台表格输出 + JSON 落盘(eval/reports/)。"""
import json
import os
from datetime import datetime

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")


def print_suite_report(suite: str, results: list[dict]) -> dict:
    """打印单个套件的明细与汇总,返回汇总 dict。

    results 元素:{id, passed, latency_ms, detail(失败原因或评分说明), extra?}"""
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n{'=' * 16} {suite} {'=' * 16}")
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        line = f"[{mark}] {r['id']}  ({r['latency_ms']}ms)"
        if r.get("score") is not None:
            line += f"  score={r['score']}"
        print(line)
        if not r["passed"] and r.get("detail"):
            print(f"       └─ {r['detail']}")
    rate = (passed / total * 100) if total else 0.0
    print(f"--- {suite}: {passed}/{total} 通过 ({rate:.0f}%) ---")
    return {"suite": suite, "passed": passed, "total": total,
            "pass_rate": round(rate, 1), "results": results}


def save_report(summaries: list[dict], model: str, meta: dict | None = None) -> str:
    """把全部套件结果写入 reports/<时间戳>.json,返回文件路径"""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(REPORTS_DIR, f"eval-{ts}.json")
    payload = {
        "timestamp": ts,
        "model": model,
        "meta": meta or {},
        "suites": summaries,
        "overall": {
            "passed": sum(s["passed"] for s in summaries),
            "total": sum(s["total"] for s in summaries),
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


async def upload_metrics(summaries: list[dict], stat_date: str | None = None) -> list[str]:
    """离线指标上板:把汇总指标写入 ai-service 的日聚合表。

    - retrieval 套件 → cx_metrics_daily.recall_at_k / precision_at_k
    - regression/quality 套件 → pe_metrics_daily.eval_pass_rate
      (按 'agent.system' 模板当前激活版本归因)

    默认 in-process 直写(复用 /v1/cx/metrics/report 端点同款实现,
    ai-service 不在线也能上报);设 EVAL_REPORT_URL 时改为 HTTP POST
    (需同时配 NESTJS_SERVICE_KEY / EVAL_REPORT_USER_ID)。
    返回已上报的套件名列表;失败仅打印,不影响评测退出码。"""
    url = os.getenv("EVAL_REPORT_URL")
    if url:
        return await _upload_via_http(summaries, url.rstrip("/"), stat_date)
    return await _upload_in_process(summaries, stat_date)


async def _upload_in_process(summaries: list[dict], stat_date: str | None) -> list[str]:
    done = []
    try:
        from app.contexteng import evaluator
        from app.db import sessionmaker
        for s in summaries:
            if s["suite"] == "retrieval":
                agg = s.get("retrieval") or {}
                if agg.get("recall_at_k") is None:
                    continue
                async with sessionmaker()() as sess:
                    await evaluator.upsert_cx_daily(
                        sess, stat_date,
                        recall_at_k=agg.get("recall_at_k"),
                        precision_at_k=agg.get("precision_at_k"))
                done.append("retrieval")
            elif s["suite"] in ("regression", "quality"):
                async with sessionmaker()() as sess:
                    await evaluator.upsert_pe_daily_eval(
                        sess, "agent.system", s["pass_rate"] / 100.0,
                        stat_date=stat_date)
                done.append(s["suite"])
    except Exception as e:
        print(f"[上报告警] in-process 写入失败(不影响评测结果): {e}")
    return done


async def _upload_via_http(summaries: list[dict], base: str, stat_date: str | None) -> list[str]:
    import httpx
    done = []
    headers = {
        "X-Service-Key": os.getenv("NESTJS_SERVICE_KEY", ""),
        "X-User-Id": os.getenv("EVAL_REPORT_USER_ID", "eval"),
    }
    for s in summaries:
        if s["suite"] == "retrieval":
            agg = s.get("retrieval") or {}
            if agg.get("recall_at_k") is None:
                continue
            body = {"kind": "retrieval", "stat_date": stat_date, **agg}
        elif s["suite"] in ("regression", "quality"):
            body = {"kind": "prompt", "template_key": "agent.system",
                    "eval_pass_rate": s["pass_rate"] / 100.0, "stat_date": stat_date}
        else:
            continue
        try:
            async with httpx.AsyncClient(timeout=30.0) as c:
                resp = await c.post(f"{base}/v1/cx/metrics/report", json=body, headers=headers)
            if resp.status_code == 200:
                done.append(s["suite"])
            else:
                print(f"[上报告警] {s['suite']} HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[上报告警] {s['suite']} 上报失败(不影响评测结果): {e}")
    return done
