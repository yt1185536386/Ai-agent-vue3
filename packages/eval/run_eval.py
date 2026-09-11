"""eval CLI 入口。

用法(必须用 ai-service 的 venv 运行):
  ../ai-service/.venv/Scripts/python run_eval.py                      # 全部套件
  ../ai-service/.venv/Scripts/python run_eval.py --suite tool_selection
  ../ai-service/.venv/Scripts/python run_eval.py --suite quality --judge qwen-max
  ../ai-service/.venv/Scripts/python run_eval.py --provider bailian --model qwen-plus
  ../ai-service/.venv/Scripts/python run_eval.py --suite retrieval --top-k 5 --threshold 0.25
  ../ai-service/.venv/Scripts/python run_eval.py --export-retrieval   # 从 cx_eval_cases 重新生成套件
"""
import argparse
import asyncio
import sys

from core.client import providers, setup
from core.judge import default_judge_model
from core.report import print_suite_report, save_report, upload_metrics
from core.runners import (
    aggregate_retrieval,
    load_suite,
    run_e2e,
    run_quality,
    run_regression,
    run_retrieval,
    run_tool_selection,
)
from core.suitegen import export_retrieval_suite

ALL_SUITES = ("tool_selection", "e2e", "quality", "regression", "retrieval")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="v3agent eval:工具选择/端到端/质量/回归/检索召回")
    p.add_argument("--suite", default="all",
                   choices=[*ALL_SUITES, "all"], help="要跑的套件,默认 all")
    p.add_argument("--provider", default="bailian", help="被测模型来源(company/bailian)")
    p.add_argument("--model", default="qwen-plus", help="被测模型")
    p.add_argument("--judge-provider", default=None, help="裁判模型来源,默认同 --provider")
    p.add_argument("--judge", default=None,
                   help="裁判模型,默认 EVAL_JUDGE_MODEL 或 qwen-max")
    p.add_argument("--no-save", action="store_true", help="不写 reports/*.json")
    p.add_argument("--no-upload", action="store_true",
                   help="不上报日聚合指标(cx_metrics_daily / pe_metrics_daily)")
    # ---- retrieval 套件专用 ----
    p.add_argument("--strategy", default=None,
                   help="检索策略标识(仅作报告标签;实际参数用 --top-k/--threshold 指定,"
                        "切分参数需先在 ai-service 侧 /v1/cx/strategy + rebuild 生效)")
    p.add_argument("--top-k", type=int, default=None, help="检索 top_k(缺省用当前策略)")
    p.add_argument("--threshold", type=float, default=None, help="相似度阈值(缺省用当前策略)")
    p.add_argument("--user-id", default="eval", help="检索目标用户(chunks 按用户隔离)")
    p.add_argument("--export-retrieval", action="store_true",
                   help="从 cx_eval_cases(enabled)导出 suites/retrieval.json 后退出")
    return p.parse_args(argv)


async def main(argv=None) -> int:
    args = parse_args(argv)
    setup()
    available = providers()
    if args.provider not in available:
        print(f"错误:来源 {args.provider!r} 未配置(可用:{list(available)})")
        return 2

    if args.export_retrieval:
        path, n = await export_retrieval_suite()
        print(f"已从 cx_eval_cases 导出 {n} 条 enabled 用例 → {path}")
        from app.db import dispose_db
        await dispose_db()
        return 0

    judge_provider = args.judge_provider or args.provider
    judge_model = args.judge or default_judge_model()

    suites = ALL_SUITES if args.suite == "all" else (args.suite,)
    print(f"被测:{args.provider}/{args.model}   裁判:{judge_provider}/{judge_model}")
    if "retrieval" in suites:
        print(f"检索策略:{args.strategy or '当前策略'}"
              f"(top_k={args.top_k or '策略默认'}, threshold={args.threshold or '策略默认'},"
              f" user={args.user_id})")

    summaries = []
    for name in suites:
        try:
            cases = load_suite(name)
        except FileNotFoundError:
            print(f"\n--- {name}: 套件文件缺失,跳过"
                  f"{'(--export-retrieval 可生成)' if name == 'retrieval' else ''} ---")
            continue
        if not cases:
            print(f"\n--- {name}: 无用例,跳过 ---")
            continue
        if name == "tool_selection":
            results = await run_tool_selection(cases, args.provider, args.model)
        elif name == "e2e":
            results = await run_e2e(cases, args.provider, args.model)
        elif name == "quality":
            results = await run_quality(cases, args.provider, args.model,
                                        judge_provider, judge_model)
        elif name == "retrieval":
            results = await run_retrieval(cases, args.provider,
                                          top_k=args.top_k, threshold=args.threshold,
                                          user_id=args.user_id)
        else:
            results = await run_regression(cases, args.provider, args.model,
                                           judge_provider, judge_model)
        summary = print_suite_report(name, results)
        if name == "retrieval":
            agg = aggregate_retrieval(results)
            summary["retrieval"] = agg
            print(f"--- retrieval 聚合:Recall@K={agg['recall_at_k']}"
                  f" Precision@K={agg['precision_at_k']}"
                  f" 零结果率={agg['zero_result_rate']} ---")
        summaries.append(summary)

    if not summaries:
        print("\n===== 无可用套件,未执行评测 =====")
        from app.db import dispose_db
        await dispose_db()
        return 2

    total_passed = sum(s["passed"] for s in summaries)
    total = sum(s["total"] for s in summaries)
    print(f"\n===== 总计:{total_passed}/{total} 通过 =====")
    meta = {"judge": f"{judge_provider}/{judge_model}"}
    if args.strategy:
        meta["strategy"] = args.strategy
    if not args.no_save:
        path = save_report(summaries, f"{args.provider}/{args.model}", meta=meta)
        print(f"报告已保存:{path}")
    if not args.no_upload:
        done = await upload_metrics(summaries)
        if done:
            print(f"离线指标已上板:{', '.join(done)}(cx/pe_metrics_daily)")
    # 释放 DB 连接池,避免退出时 aiomysql 在已关闭的事件循环上报析构异常
    from app.db import dispose_db
    await dispose_db()
    return 0 if total_passed == total else 1


if __name__ == "__main__":
    # Windows 控制台默认 GBK,强制 UTF-8 输出防止中文乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(asyncio.run(main()))
