"""Agent 业务装配层(薄)。

仓库工具组、用户权限工具组与入口守门子图已随旧权限体系一并移除
(2026-08 权限重构:旧 roles/temp_permissions 体系废除),
Agent = 基础工具 + (有 embed 配置时)RAG 检索工具。

运行框架在本包(app/agent/:模型客户端 / prompt / ReAct 循环 / SSE / 加工),
基础工具在 app/tools/;公开符号统一由 app/agent/__init__.py 再导出。
"""
from app.agent.client import build_chat
from app.agent.loop import make_agent
from app.tools import (
    BASE_TOOLS,
    build_external_kb_tool,
    build_query_team_members_tool,
    build_rag_tool,
    build_team_member_tool,
)


def build_agent(
    provider: dict,
    model: str,
    body: dict,
    *,
    user_id: str | None = None,
    embed_provider: dict | None = None,
    embed_model: str = "text-embedding-v3",
    checkpointer=None,
    guardrail_enabled: bool | None = None,
):
    """按来源与请求参数构建 ReAct Agent(带工具)。
    user_id + embed_provider 齐备时附加 RAG 检索工具(Agent 自主决定是否检索)。
    guardrail_enabled:守门子图已移除,该参数仅为兼容 eval 调用方保留,无效果。

    第二阶段:改用 make_agent 手写循环;想对比 prebuilt 行为时,
    把最后一行换回 create_react_agent(build_chat(...), tools) 即可。"""
    tools = list(BASE_TOOLS)
    if user_id and embed_provider and embed_provider.get("base_url"): # 如果有嵌入配置
        tools.append(build_rag_tool(user_id, embed_provider, embed_model)) # 添加 RAG 工具
    # 普通提问:不添加 RAG 工具
    # 外部知识库工具:仅当配置了 rag-service 地址时挂载(把一个独立知识库挂载进来,Agent 按场景触发)
    import os
    if user_id and os.getenv("RAG_SERVICE_BASE_URL"):
        tools.append(build_external_kb_tool(user_id))

    # HITL 写工具:配置了 NestJS 业务地址与内部密钥时挂载"调整团队成员职级"。
    # 该工具在内部 interrupt 挂起走人工审批,审批通过后调 NestJS users 接口落库。
    if user_id and os.getenv("NESTJS_SERVICE_BASE_URL") and os.getenv("NESTJS_SERVICE_KEY"):
        # 只读查询:查可见团队成员(供模型回答"我的团队成员/某部门成员")
        tools.append(build_query_team_members_tool(user_id))
        # 写操作:调整成员职级(人工审批后执行)
        tools.append(build_team_member_tool(user_id))

    return make_agent(build_chat(provider, model, body), tools, checkpointer)


async def init_observability() -> None:
    """启动时装配观测体系:把 prompteng / contexteng 的实现注入 harness 裸钩子。

    harness 只定义注入点(模板加载器 / 装配观测器 / context 快照观测器),
    不 import 业务模块;这里完成接线并预热模板缓存(activate 的 DB 模板
    立即对主链路生效)。观测体系装配失败仅降级为无观测,不影响启动。"""
    import logging
    log = logging.getLogger(__name__)
    from app.contexteng import collector
    from app.agent.loop import set_context_observer
    from app.agent.prompts import set_prompt_observer, set_template_loader
    from app.prompteng import service as pe_service

    set_template_loader(pe_service.load_content)
    set_prompt_observer(pe_service.record_assembly)
    set_context_observer(collector.report_model_call)
    try:
        await pe_service.refresh_cache()
    except Exception:
        log.warning("prompt 模板缓存预热失败(降级为代码默认 prompt)", exc_info=True)
