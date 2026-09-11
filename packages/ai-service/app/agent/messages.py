"""消息转换与响应载荷:OpenAI dict ↔ LangChain 消息、响应构造、格式标记。"""
import time
import uuid

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

# 标题 / 列表 / 引用 / 代码块 / 表格 / 加粗 / 链接 / 图片等 Markdown 语法特征
_MD_PATTERN = (
    r"(^|\n)\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>\s)"
    r"|```|(\|[^|\n]+\|){2,}|\*\*[^*\n]+\*\*|\[[^\]\n]+\]\([^)\n]+\)"
)


def mark_content_format(payload: dict) -> dict:
    """在助手消息上写入 content_format 标识(原 NestJS markContentFormat 逻辑)"""
    import re
    rx = re.compile(_MD_PATTERN)
    for choice in (payload.get("choices") or []):
        msg = choice.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            msg["content_format"] = "markdown" if rx.search(content) else "text"
    return payload


def to_lc_message(m: dict):
    """OpenAI 消息 dict → LangChain 消息(多模态 content 列表原样传入)"""
    role = m.get("role")
    content = m.get("content", "")
    if role == "system":
        return SystemMessage(content=content)
    if role == "assistant":
        return AIMessage(content=content)
    if role == "tool":
        return ToolMessage(content=content, tool_call_id=m.get("tool_call_id", ""))
    return HumanMessage(content=content)


def completion_payload(model: str, answer: str) -> dict:
    """构造 OpenAI 兼容的非流式响应"""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
    }
