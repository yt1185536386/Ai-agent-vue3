"""Agent 运行框架(与业务无关的 ReAct 循环 + SSE + 加工层)。

文件地图(学习顺序):
- client.py     模型客户端(ThinkingChatOpenAI / build_chat)——先看这,理解调用怎么走网关
- prompts.py    系统提示词(时间注入 + 业务规则注册表 + 模板注入点)
- loop.py       ReAct 循环核心(make_agent + checkpointer + context 快照观测)
- stream.py     SSE 事件流运行器(token/reasoning/tool/HITL/卡片钩子)
- messages.py   OpenAI dict ↔ LangChain 消息转换与响应载荷
- preprocess.py 请求体加工(时间/联网搜索/思考模式规整)
- assembly.py   业务装配(工具组选择 + 观测体系接线)——把本框架与 tools/prompteng/contexteng 缝合

从哪里入手学习:client → loop → stream,读完这三个就懂了 Agent 主链路。
"""
from app.agent.client import EXTRA_MODEL_PARAMS, ThinkingChatOpenAI, build_chat
from app.agent.loop import get_checkpointer, make_agent
from app.agent.messages import (
    completion_payload,
    mark_content_format,
    to_lc_message,
)
from app.agent.preprocess import (
    apply_provider_search,
    inject_time,
    normalize_thinking,
    preprocess,
    time_system_message,
)
from app.agent.prompts import (
    agent_system_prompt,
    register_rules,
    registered_rules,
)
from app.agent.stream import (
    register_card_hook,
    run_agent_non_stream,
    run_agent_stream,
    sse_event,
)
from app.agent.assembly import build_agent, init_observability

__all__ = [
    "EXTRA_MODEL_PARAMS", "ThinkingChatOpenAI", "build_chat",
    "get_checkpointer", "make_agent",
    "completion_payload", "mark_content_format", "to_lc_message",
    "apply_provider_search", "inject_time", "normalize_thinking", "preprocess",
    "time_system_message",
    "agent_system_prompt", "register_rules", "registered_rules",
    "register_card_hook", "run_agent_non_stream", "run_agent_stream", "sse_event",
    "build_agent", "init_observability",
]
