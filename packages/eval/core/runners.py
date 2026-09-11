"""四个评测套件的执行器。每个 run_* 返回 report.print_suite_report 需要的 results。

用例格式见 suites/*.json 与 README.md。
"""
import json
import os
import re
import time
import uuid

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from core.client import build_eval_agent, providers
from core.judge import judge_answer

SUITES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "suites")

# 套件名 → 文件名(不一致的特例;e2e 的用例文件叫 e2e_flows.json)
_SUITE_FILES = {"e2e": "e2e_flows.json"}


def load_suite(name: str) -> list[dict]:
    with open(os.path.join(SUITES_DIR, _SUITE_FILES.get(name, f"{name}.json")), encoding="utf-8") as f:
        return json.load(f)


def _final_text(result: dict) -> str:
    msg = result["messages"][-1]
    c = msg.content
    if not isinstance(c, str):
        c = "".join(p.get("text", "") for p in c if isinstance(p, dict))
    return c


def _tool_calls_of(messages: list) -> list[str]:
    """从消息序列里按顺序提取全部工具调用名"""
    names = []
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            names.extend(tc["name"] for tc in m.tool_calls)
    return names


def _is_subsequence(expect: list, actual: list) -> bool:
    """期望序列是实际序列的子序列(允许模型穿插其他合理调用,如 get_current_time)"""
    it = iter(actual)
    return all(e in it for e in expect)


def _new_config(tag: str) -> dict:
    return {"configurable": {"thread_id": f"eval-{tag}-{uuid.uuid4().hex[:8]}"}}


# ---------- 1. 工具选择准确率 ----------

async def run_tool_selection(cases: list[dict], provider_key: str, model: str) -> list[dict]:
    """单轮输入 → 断言模型调用了期望的工具序列(默认子序列匹配)"""
    results = []
    for c in cases:
        t0 = time.perf_counter()
        try:
            agent = build_eval_agent(
                provider_key, model,
                user_id=c.get("user_id", "eval"),
                checkpointer=MemorySaver(),
            )
            out = await agent.ainvoke(
                {"messages": [HumanMessage(content=c["input"])]},
                config=_new_config("ts"),
            )
            actual = _tool_calls_of(out["messages"])
            expect = c["expect"]
            if c.get("match", "subsequence") == "exact":
                ok = actual == expect
            else:
                ok = _is_subsequence(expect, actual)
            detail = "" if ok else f"期望 {expect},实际 {actual}"
            results.append({"id": c["id"], "passed": ok,
                            "latency_ms": int((time.perf_counter() - t0) * 1000),
                            "detail": detail})
        except Exception as e:
            results.append({"id": c["id"], "passed": False,
                            "latency_ms": int((time.perf_counter() - t0) * 1000),
                            "detail": f"执行异常: {e}"})
    return results


# ---------- 2. 端到端流程成功率 ----------

async def run_e2e(cases: list[dict], provider_key: str, model: str) -> list[dict]:
    """多轮脚本:逐步发消息、断言工具序列;撞 interrupt 时按 step.approve 自动审批。

    用例:{id, user_id?, steps:[{user, expect_tools?, approve?}],
          expect_final_contains?}
    """
    results = []
    for c in cases:
        t0 = time.perf_counter()
        failures = []
        try:
            agent = build_eval_agent(
                provider_key, model,
                user_id=c.get("user_id", "eval"),
                checkpointer=MemorySaver(),
            )
            config = _new_config("e2e")
            final_text = ""
            prev_count = 0  # 已检查过的消息数,工具断言只看本步新增
            for i, step in enumerate(c["steps"]):
                out = await agent.ainvoke(
                    {"messages": [HumanMessage(content=step["user"])]}, config=config)
                # HITL:图挂起时按本步策略自动批准/拒绝
                interrupts = out.get("__interrupt__") if isinstance(out, dict) else None
                if interrupts:
                    if not step.get("approve"):
                        failures.append(f"步骤{i + 1}: 出现未预期的审批中断")
                        break
                    decision = "approve" if step.get("approve") else "reject"
                    resume = {intr.id: decision for intr in interrupts}
                    out = await agent.ainvoke(Command(resume=resume), config=config)
                expect = step.get("expect_tools", [])
                if expect:
                    new_msgs = out["messages"][prev_count:]
                    actual = _tool_calls_of(new_msgs)
                    if not _is_subsequence(expect, actual):
                        failures.append(f"步骤{i + 1}: 期望工具 {expect},实际 {actual}")
                prev_count = len(out["messages"])
                final_text = _final_text(out)
            needle = c.get("expect_final_contains")
            if needle and needle not in final_text:
                failures.append(f"最终回答未包含「{needle}」: {final_text[:120]}")
        except Exception as e:
            failures.append(f"执行异常: {e}")
        results.append({"id": c["id"], "passed": not failures,
                        "latency_ms": int((time.perf_counter() - t0) * 1000),
                        "detail": "; ".join(failures)})
    return results


# ---------- 3. 回答质量 LLM 评分 ----------

async def run_quality(cases: list[dict], provider_key: str, model: str,
                      judge_provider_key: str, judge_model: str) -> list[dict]:
    """跑 Agent 取最终回答 → 裁判模型按 rubric 打 1-5 分 → >= pass_score 判过"""
    judge_provider = providers()[judge_provider_key]
    results = []
    for c in cases:
        t0 = time.perf_counter()
        try:
            agent = build_eval_agent(
                provider_key, model,
                user_id=c.get("user_id", "eval"),
                checkpointer=MemorySaver(),
            )
            out = await agent.ainvoke(
                {"messages": [HumanMessage(content=c["input"])]},
                config=_new_config("q"),
            )
            answer = _final_text(out)
            verdict = await judge_answer(
                judge_provider, judge_model, c["input"], c["rubric"], answer)
            pass_score = c.get("pass_score", 4)
            ok = verdict["score"] >= pass_score
            results.append({"id": c["id"], "passed": ok,
                            "latency_ms": int((time.perf_counter() - t0) * 1000),
                            "score": verdict["score"],
                            "detail": "" if ok else
                                      f"{verdict['reason']} | 回答: {answer[:120]}"})
        except Exception as e:
            results.append({"id": c["id"], "passed": False,
                            "latency_ms": int((time.perf_counter() - t0) * 1000),
                            "detail": f"执行异常: {e}"})
    return results


# ---------- 5. 检索召回评测(Retrieval Recall@K / Precision@K) ----------

async def run_retrieval(cases: list[dict], provider_key: str, *,
                        top_k: int | None = None, threshold: float | None = None,
                        user_id: str = "eval") -> list[dict]:
    """检索离线评测:in-process 调 search_chunks(与线上同一实现),
    对 ground truth 计算 Recall@K / Precision@K / 零结果率。

    用例:{id, query, expect_doc_ids?, expect_contains?, user_id?}
    (由 suites/retrieval.json 提供;run_eval --export-retrieval 可从
    cx_eval_cases 重新导出)。top_k/threshold 缺省用当前检索策略,
    指定即可在同一份 ground truth 上对比多策略。

    单条 passed 判据:recall == 1(期望文档全部命中)且内容断言通过;
    聚合指标(recall_at_k 等)挂在每条结果的 recall/precision 字段上,
    由 run_eval 汇总后上报 cx_metrics_daily。"""
    from app.contexteng import strategy as cx_strategy
    from app.contexteng.evaluator import _score_case
    from app.db import sessionmaker
    from app.rag import embed_texts, search_chunks
    cfg = cx_strategy.current()
    k = top_k if top_k is not None else cfg["top_k"]
    th = threshold if threshold is not None else cfg["threshold"]
    provider = providers()[os.getenv("EMBED_PROVIDER", "bailian")]
    embed_model = os.getenv("EMBED_MODEL", "text-embedding-v3")
    results = []
    async with sessionmaker()() as s:
        for c in cases:
            t0 = time.perf_counter()
            try:
                embs = await embed_texts(provider, embed_model, [c["query"]])
                hits = await search_chunks(s, c.get("user_id") or user_id,
                                           embs[0], top_k=k)
                hits = [h for h in hits if h.get("score", 0) > th]
                scored = _score_case(
                    {"expect_doc_ids": json.dumps(c.get("expect_doc_ids", [])),
                     "expect_contains": json.dumps(c.get("expect_contains", []))},
                    hits, k)
                recall = scored["recall"]
                passed = (recall is None or recall >= 1.0) \
                    and scored["contains_ok"] is not False
                detail = "" if passed else (
                    f"recall={recall} 命中 {[h['doc_id'] for h in hits]},"
                    f"期望 {c.get('expect_doc_ids', [])}")
                results.append({"id": c["id"], "passed": passed,
                                "latency_ms": int((time.perf_counter() - t0) * 1000),
                                "score": recall,
                                "recall": recall, "precision": scored["precision"],
                                "hit_count": scored["hit_count"],
                                "detail": detail})
            except Exception as e:
                results.append({"id": c["id"], "passed": False,
                                "latency_ms": int((time.perf_counter() - t0) * 1000),
                                "recall": None, "precision": 0.0, "hit_count": 0,
                                "detail": f"执行异常: {e}"})
    return results


def aggregate_retrieval(results: list[dict]) -> dict:
    """把 run_retrieval 的逐条结果聚合为 Recall@K / Precision@K / 零结果率"""
    recalls = [r["recall"] for r in results if r.get("recall") is not None]
    precisions = [r["precision"] for r in results]
    zero_n = sum(1 for r in results if r.get("hit_count", 0) == 0)
    return {
        "recall_at_k": round(sum(recalls) / len(recalls), 4) if recalls else None,
        "precision_at_k": round(sum(precisions) / len(precisions), 4) if precisions else None,
        "zero_result_rate": round(zero_n / len(results), 4) if results else None,
    }


# ---------- 4. Prompt 回归测试 ----------


async def run_regression(cases: list[dict], provider_key: str, model: str,
                         judge_provider_key: str, judge_model: str) -> list[dict]:
    """固定问答对断言:contains / regex / judge。

    走直答路径(build_chat + 时间注入,与线上 preprocess 一致),
    用于改动系统提示词或切换模型后的防退化对比。"""
    from app.harness import build_chat, preprocess, to_lc_message
    provider = providers()[provider_key]
    judge_provider = providers()[judge_provider_key]
    results = []
    for c in cases:
        t0 = time.perf_counter()
        try:
            body = preprocess(
                {"model": model, "messages": [{"role": "user", "content": c["input"]}]},
                provider,
            )
            chat = build_chat(provider, model, body)
            resp = await chat.ainvoke([to_lc_message(m) for m in body["messages"]])
            answer = resp.content if isinstance(resp.content, str) else "".join(
                b.get("text", "") for b in resp.content if isinstance(b, dict))
            assertion = c["assert"]
            atype, value = assertion["type"], assertion["value"]
            score = None
            if atype == "contains":
                ok = value in answer
                detail = "" if ok else f"回答未包含「{value}」: {answer[:120]}"
            elif atype == "regex":
                ok = bool(re.search(value, answer))
                detail = "" if ok else f"回答未匹配 /{value}/: {answer[:120]}"
            elif atype == "judge":
                verdict = await judge_answer(judge_provider, judge_model,
                                             c["input"], value, answer)
                score = verdict["score"]
                ok = score >= assertion.get("pass_score", 4)
                detail = "" if ok else f"{verdict['reason']} | 回答: {answer[:120]}"
            else:
                ok, detail = False, f"未知断言类型: {atype}"
            results.append({"id": c["id"], "passed": ok,
                            "latency_ms": int((time.perf_counter() - t0) * 1000),
                            "score": score, "detail": detail})
        except Exception as e:
            results.append({"id": c["id"], "passed": False,
                            "latency_ms": int((time.perf_counter() - t0) * 1000),
                            "detail": f"执行异常: {e}"})
    return results
