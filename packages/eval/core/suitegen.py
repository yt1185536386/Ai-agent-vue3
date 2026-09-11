"""suites/retrieval.json 生成器:从 cx_eval_cases 导出(enabled 用例)。

线上回收(零结果/低分 query)与人工标注的用例统一沉淀在
cx_eval_cases 表;本模块把 enabled 用例导出为离线套件文件,
保证「线上回收 → 离线评测」闭环可重复执行。
"""
import json
import os

SUITES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "suites")


async def export_retrieval_suite(filename: str = "retrieval.json") -> tuple[str, int]:
    """导出 enabled 用例到 suites/<filename>,返回 (路径, 用例数)"""
    from sqlalchemy import select
    from app.contexteng.models import CxEvalCase
    from app.db import sessionmaker

    async with sessionmaker()() as s:
        rows = (await s.execute(
            select(CxEvalCase).where(CxEvalCase.status == "enabled")
            .order_by(CxEvalCase.created_at)
        )).scalars().all()
    cases = [{
        "id": c.id,
        "query": c.query,
        "expect_doc_ids": json.loads(c.expect_doc_ids or "[]"),
        "expect_contains": json.loads(c.expect_contains or "[]"),
        "source": c.source,
    } for c in rows]
    path = os.path.join(SUITES_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
    return path, len(cases)
