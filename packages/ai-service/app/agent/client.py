"""模型客户端层:构造 LangChain ChatOpenAI(走 OpenAI 兼容网关)。

只关心「怎么调模型」,不关心工具、prompt、循环。
"""
from langchain_openai import ChatOpenAI

# 从请求体中提取、需要转给模型的额外参数(而非 OpenAI 标准字段)
EXTRA_MODEL_PARAMS = ("enable_search", "enable_thinking")


class ThinkingChatOpenAI(ChatOpenAI):
    """修补 langchain_openai 1.4 的行为变化:
    上游 delta 里的 reasoning_content 不再被提取进 additional_kwargs
    (官方建议用厂商子类,但我们走 OpenAI 兼容网关,没有现成子类)。
    这里重写 chunk 转换,把思考内容放回 additional_kwargs,
    让下游(流式 SSE / 非流式响应)可以统一从 additional_kwargs 读取。"""

    def _convert_chunk_to_generation_chunk(
        self, chunk: dict, default_chunk_class, base_generation_info
    ):
        gen = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        choices = chunk.get("choices") or chunk.get("chunk", {}).get("choices") or []
        if gen is not None and choices:
            reasoning = (choices[0].get("delta") or {}).get("reasoning_content")
            if reasoning:
                gen.message.additional_kwargs["reasoning_content"] = reasoning
        return gen


def build_chat(provider: dict, model: str, body: dict):
    """无工具的纯 ChatOpenAI 客户端(用于无 tools 路径,统一走 LangChain)。

    provider 带 key 时经 X-Channel-Key 头传给 Java 模型网关做渠道路由;
    带 user_id/username 时一并透传,供网关做用户维度限流/计量;
    带 request_id 时透传全链路请求 ID,网关侧落 invoke_logs 供排障关联。
    """
    extra_body = {k: body[k] for k in EXTRA_MODEL_PARAMS if k in body}
    default_headers = {}
    if provider.get("key"):
        default_headers["X-Channel-Key"] = provider["key"]
    if provider.get("user_id"):
        default_headers["X-User-Id"] = provider["user_id"]
    if provider.get("username"):
        default_headers["X-Username"] = provider["username"]
    if provider.get("request_id"):
        default_headers["X-Request-Id"] = provider["request_id"]
    return ThinkingChatOpenAI(
        model=model,
        api_key=provider["api_key"] or "not-needed",
        base_url=provider["base_url"],
        temperature=0,
        **({"extra_body": extra_body} if extra_body else {}),
        **({"default_headers": default_headers} if default_headers else {}),
    )
