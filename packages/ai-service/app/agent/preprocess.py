"""请求体加工层:时间注入 / 联网搜索 / 思考模式规整(原 NestJS 下沉的逻辑)。"""
import os

from app.agent.prompts import time_system_message


def inject_time(messages: list) -> list:
    """在消息列表最前插入时间系统消息"""
    return [time_system_message(), *(messages or [])]


def apply_provider_search(body: dict, provider: dict) -> dict:
    """按来源是否开启联网搜索补 enable_search"""
    if provider.get("enable_search"):
        body = {**body, "enable_search": True}
    return body


def normalize_thinking(body: dict, provider: dict, model: str) -> dict:
    """思考模式改为「显式开启」:
    - 当前模型不支持思考时剔除 enable_thinking,避免上游报错
      (通过 THINKING_MODELS 名称匹配判断,默认 k3/qwen3/deepseek 支持);
    - 支持思考但未显式传参时默认补 False —— qwen3/deepseek/k3 等
      思考型模型上游默认开思考,只有前端开关显式传 true 才开启。"""
    thinking_models = os.getenv("THINKING_MODELS", "k3,qwen3,deepseek") # 支持思考的模型
    supported = "*" in thinking_models or any(  # 是否支持思考
        p.strip() and p.strip() in model.lower()  # 模型名称匹配
        for p in thinking_models.split(","))  # 遍历支持思考的模型
    if not supported:  # 当前模型不支持思考
        # 剔除 enable_thinking,避免上游报错
        if "enable_thinking" in body:  # 存在 enable_thinking 字段
            body = {k: v for k, v in body.items() if k != "enable_thinking"}  # 剔除 enable_thinking 字段
        return body  # 返回加工后的请求体
    if "enable_thinking" not in body:  # 未显式传参
        # 思考型模型上游默认开思考,只有前端开关显式传 true 才开启
        # 所以默认补 False
        body = {**body, "enable_thinking": False}  # 补 False
    return body


def preprocess(body: dict, provider: dict) -> dict:
    """把 NestJS 之前做的加工集中到 AI 服务层;
    RAG 检索已工具化(search_docs),不在此处强制注入"""
    msgs = list(body.get("messages", [])) # 消息列表
    body = {**body, "messages": inject_time(msgs)} # 时间注入
    body = apply_provider_search(body, provider) # 联网搜索
    body = normalize_thinking(body, provider, body.get("model", "")) # 思考模式规整
    return body
