"""LLM 评分器:按 rubric 给回答打 1-5 分,返回 {score, reason}。

评分模型与被测模型解耦(可用更强的模型当裁判),
通过 --judge 参数或 EVAL_JUDGE_MODEL 环境变量指定。
"""
import json
import os

from langchain_core.messages import HumanMessage

_JUDGE_PROMPT = """你是一个严格的 AI 回答质量评审。请根据「评分要点」给「待评回答」打分。

【用户问题】
{question}

【评分要点】
{rubric}

【待评回答】
{answer}

要求:
1. 只依据评分要点评判,不要引入自己的额外标准;
2. 打分 1-5 的整数:5=完全满足全部要点,3=满足主要要点但有明显缺漏,1=基本未满足;
3. 用如下 JSON 格式输出,不要输出任何其他内容:
{{"score": <1-5>, "reason": "<一两句话说明扣分点或满分理由>"}}"""


async def judge_answer(provider: dict, judge_model: str,
                       question: str, rubric: str, answer: str) -> dict:
    """返回 {"score": int, "reason": str};解析失败时 score=0 并带原始输出"""
    from app.agent import build_chat
    chat = build_chat(provider, judge_model, {})
    prompt = _JUDGE_PROMPT.format(question=question, rubric=rubric, answer=answer)
    resp = await chat.ainvoke([HumanMessage(content=prompt)])
    text = resp.content if isinstance(resp.content, str) else "".join(
        b.get("text", "") for b in resp.content if isinstance(b, dict))
    # 思考型裁判模型的回答可能带 <think> 段或 ```json 围栏,取最后一个 JSON 对象
    import re
    matches = re.findall(r"\{[^{}]*\"score\"[^{}]*\}", text, re.S)
    if matches:
        try:
            parsed = json.loads(matches[-1])
            return {"score": int(parsed.get("score", 0)),
                    "reason": str(parsed.get("reason", ""))}
        except (ValueError, TypeError):
            pass
    return {"score": 0, "reason": f"裁判输出解析失败: {text[:200]}"}


def default_judge_model() -> str:
    return os.getenv("EVAL_JUDGE_MODEL", "qwen-max")
