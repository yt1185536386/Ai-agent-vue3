"""
AI 服务层(FastAPI + LangChain Agent + 会话持久化 + RAG)。

职责:
- 模型调用(OpenAI 兼容,转发到外部来源)
- Agent 编排(工具调用循环)
- 参数加工(时间注入/联网搜索/思考模式剔除)
- 会话与消息持久化(SQLite)
- 文档上传 + 分块 + Embedding + 简单相似度检索

文件按「一次请求的执行顺序」排列,自上而下读 = 请求的完整生命周期:

    [启动] lifespan(建 HTTP 客户端/建表/加载模型来源/装配观测)
       ↓
    [入口] chat_completions(鉴权 → 选模型来源 → 预处理 → 分流)
       ├─ Agent 分支(tools/use_agent): run_agent
       │     ├─ _fork_for_regenerate   regenerate 时间旅行分叉
       │     ├─ run_agent_stream       流式 ReAct 循环(agent 包)
       │     ├─ run_agent_non_stream   非流式 ReAct 循环(agent 包)
       │     └─ persist_*              双轨落库(persistence 包)
       └─ 直答分支: forward_upstream
             └─ build_chat             纯模型调用(agent 包)

    [旁路] /v1/conversations* 会话 CRUD → /v1/documents* 文档与 RAG → /v1/asr* 语音
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import (
    Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile,
)
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from langgraph.types import Command

from app.agent import (
    build_agent,
    build_chat,
    completion_payload,
    get_checkpointer,
    init_observability,
    mark_content_format,
    preprocess,
    run_agent_non_stream,
    run_agent_stream,
    sse_event as sse_event_bytes,
    to_lc_message,
)
from app.core.db import (
    count_messages,
    create_conv, create_tables, delete_conv,
    get_session, init_db, insert_message, list_user_convs,
    serialize_conv, serialize_msg, sessionmaker,
)
from app.core.deps import require_service_key
from app.providers.registry import PROVIDERS, get_provider, refresh_providers
from app.persistence.display import (
    get_owned_conv, load_display_history,
    persist_assistant_message, persist_user_message, truncate_display,
)
from app.rag.engine import Document, ingest_document, search_chunks, embed_texts

# 注册 pe_*/cx_* 表到 Base.metadata(create_tables 建表用)
import app.prompteng.models  # noqa: F401
import app.contexteng.models  # noqa: F401
from app.prompteng.api import router as pe_router
from app.contexteng.api import router as cx_router
from app.contexteng import collector as cx_collector

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

log = logging.getLogger(__name__)

# root logger 默认 WARNING,不显式开启的话 INFO 级日志(控制台和落库)全被吞掉
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s - %(message)s")

# MySQL 运行日志(写入 log_ai_service 表):DATABASE_URL 非 MySQL 时自动跳过,失败静默降级
from app.dblog import attach_mysql_logging  # noqa: E402

attach_mysql_logging()

# 模型来源统一以 model-gateway channels 表为准(见 app/providers/registry.py),
# PROVIDERS 为进程内缓存(15s TTL,原地刷新),环境变量仅作查库失败时的兜底

# NestJS 网关调用 AI 服务时的内部鉴权密钥
NESTJS_SERVICE_KEY = os.getenv("NESTJS_SERVICE_KEY")


# ============================================================
# [启动] 进程启动时执行一次,之后才是任何请求
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=15.0))
    init_db(os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./ai_service.db"))
    await create_tables()
    # 启动即从 channels 表加载模型来源(失败则保留环境变量兜底,运行期靠 TTL 自愈)
    await refresh_providers(force=True)
    # 装配观测体系:harness 裸钩子 ← prompteng/contexteng 实现,并预热模板缓存
    await init_observability()
    # 文件上传目录
    os.makedirs(os.getenv("UPLOAD_DIR", "./uploads"), exist_ok=True)
    yield
    await app.state.http.aclose()


app = FastAPI(title="AI Service", lifespan=lifespan)
app.include_router(pe_router)   # /v1/pe/*  Prompt 工程
app.include_router(cx_router)   # /v1/cx/*  Context 工程


# ============================================================
# [通用] 两条分支共用的错误格式与运维端点
# ============================================================


def openai_error(message: str, status: int) -> JSONResponse:
    """统一 OpenAI 兼容错误格式(前端 SDK 只解析 error 字段)"""
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": "ai_service_error", "param": None, "code": None}},
    )


def current_user_id(x_user_id: str | None = Header(default=None)) -> str:
    """保留旧依赖名但仅用于 /health 等公开端点;受保护端点统一用 require_service_key。"""
    return x_user_id or "default"


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "providers": list(PROVIDERS)}


# ============================================================
# [入口] 聊天补全:所有聊天请求的唯一入口,读头 → 鉴权 → 选来源 → 分流
# ============================================================


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    x_provider: str = Header(default="company"),
    x_username: str = Header(default=""),
    x_request_id: str | None = Header(default=None),
    user_id: str = Depends(require_service_key),
):
    provider = await get_provider(x_provider) # 获取模型来源(channels 表为准)
    if not provider:
        return openai_error(f"未知的模型来源: {x_provider}", 400)
    # 每次请求拷贝一份并注入用户身份:build_chat/embed_texts 会把它
    # 经 X-User-Id / X-Username 头透传给 Java 模型网关作用户维度限流/计量;
    # request_id 同样透传,让 NestJS → ai-service → Java 全链路日志可按 ID 关联
    provider = {**provider, "user_id": user_id, "username": x_username,
                "request_id": x_request_id}

    body = await request.json() # 解析请求体
    # 观测上下文绑定:工具调用/钩子回调经 contextvar 读取 user_id 与会话 ID
    cx_collector.bind_request_context(user_id, body.get("conversation_id") or "")
    # RAG 已工具化(第一阶段 1.2):不再强制检索注入,
    # 由 Agent 通过 search_docs 工具自主决定是否检索用户文档
    body = preprocess(body, provider) # 预处理请求体

    # 带 tools 或显式 use_agent 的请求走服务端 Agent(工具调用循环在 AI 服务层完成);
    # 来源不支持 tool_calls 时自动回落直答,前端可以无脑默认开 Agent
    if (body.get("tools") or body.get("use_agent")) and provider.get("supports_tools"): # 是否支持工具调用
        return await run_agent(request, provider, body, user_id) # 走服务端 Agent

    return await forward_upstream(request, provider, body, user_id) # 转发到上游模型


def _message_text(m) -> str:
    """提取 LC 消息的纯文本(content 为列表时拼 text block)。
    Agent 与直答两条分支落库前都要用它,故放在两分支之前。"""
    if isinstance(m.content, str):
        return m.content
    return "".join(
        b.get("text", "") for b in m.content if isinstance(b, dict)
    )


# ============================================================
# [分支一] 服务端 Agent:ReAct 循环 + HITL + regenerate 分叉
# ============================================================


async def run_agent(request: Request, provider: dict, body: dict, user_id: str):    # 服务端 Agent
    """服务端 Agent:ReAct 循环(决策 → 工具 → 最终回答),OpenAI 兼容输出。
    Agent 路径强制关闭来源自带的 enable_search:联网检索应由显式工具完成,
    否则模型会绕过工具直接用内置搜索回答,工具调用形同虚设。

    会话持久化(所有权收敛):checkpoint 是推理轨道唯一权威,messages 表是
    展示轨道唯一权威,两端写入都在服务端完成。前端只发本轮新消息;
    无 conversation_id 为 adhoc 模式(不落库,eval/冒烟用)。

    HITL(人机回环):
    - conversation_id 作为 LangGraph thread_id,断点状态存 checkpoints.db;
    - body.resume.decision 存在时,不读 messages,从断点恢复执行
      (前端审批卡片点「批准/拒绝」后走的分支);
    - body.regenerate.keep 存在时,checkpoint 时间旅行分叉重跑。"""

    ### 预处理请求体-----------------------
    body.pop("enable_search", None) # 关闭来源自带的 enable_search
    model = body.get("model", "")  # 获取模型名称
    embed_provider = PROVIDERS.get(os.getenv("EMBED_PROVIDER", "bailian")) # 获取嵌入模型来源
    if embed_provider:
        # 与 chat 来源一样注入用户身份,透传给 Java 模型网关做计量
        embed_provider = {**embed_provider,
                          "user_id": provider.get("user_id", ""),
                          "username": provider.get("username", "")}

    # 构建 Agent-----------------------
    agent = build_agent(
        provider, # 模型来源
        model, # 模型名称
        body, # 请求体
        user_id=user_id, # 用户 ID
        embed_provider=embed_provider, # 嵌入模型来源
        embed_model=os.getenv("EMBED_MODEL", "text-embedding-v3"), # 嵌入模型名称
        checkpointer=await get_checkpointer(), # 状态检查点
    )

    conv_id = body.get("conversation_id") # 会话 id;缺失 = adhoc 模式(不落库)
    thread_id = conv_id or f"adhoc-{os.urandom(8).hex()}" # 确定档案编号,这次对话用哪个档案夹？
    config = {"configurable": {"thread_id": thread_id}} # 把编号装进 LangGraph 要求的格式
    decision = (body.get("resume") or {}).get("decision") # 判断这次请求是不是"审批恢复"
    if decision:
        # 恢复:把审批决策发给每个挂起的 interrupt(多个并行写工具时逐个送达)
        state = await agent.aget_state(config) # 获取状态
        ids = [
            intr.id
            for task in (state.tasks or [])
            for intr in (task.interrupts or [])
        ]
        if not ids:
            return openai_error("没有待审批的操作(断点不存在或已完成)", 400)
        # 审批恢复:不读 messages,拿钥匙开柜,从断点继续执行
        graph_input = Command(resume={i: decision for i in ids})
    else:
        incoming = [to_lc_message(m) for m in body.get("messages", [])] # 转换为 LC 格式
        # 时间/仓库规则的系统提示由 agent_node 调用模型时现注入,
        # 请求体里的系统消息不入图(避免在 checkpoint 里过期、逐轮累加)
        incoming = [m for m in incoming if m.type != "system"] # 过滤掉系统消息
        regen = body.get("regenerate") or None
        state_msgs = None   # checkpoint 历史(守门分类上下文用)
        new_msgs = incoming # 本轮真正的新消息(守门判定用;不含回填历史)

        if not conv_id:
            # adhoc 模式:不落库、不回填、不支持 regenerate(每次新 thread)
            graph_input = {"messages": incoming}
        else:
            async with sessionmaker()() as s:
                if not await get_owned_conv(s, conv_id, user_id):
                    return openai_error("会话不存在", 404)

                if regen:
                    try:
                        config = await _fork_for_regenerate(
                            agent, config, int(regen.get("keep", 0)))
                    except ValueError as e:
                        return openai_error(str(e), 400)
                    new_msgs = []
                    graph_input = {"messages": []}
                else:
                    state = await agent.aget_state(config) # 获取状态
                    state_msgs = (state.values or {}).get("messages") or None
                    # 老客户端守卫:checkpoint 已有历史时只认最后一条 human,
                    # 防止旧前端全量重发造成重复累加
                    if state_msgs and len(incoming) > 1:
                        incoming = incoming[-1:]
                        new_msgs = incoming
                    # 本轮新消息进图前落展示轨道(图失败/终止用户消息不丢)
                    if new_msgs and new_msgs[-1].type == "human":
                        await persist_user_message(
                            conv_id, _message_text(new_msgs[-1]),
                            body.get("attachments"))
                    if not state_msgs:
                        # 老会话一次性回填:展示轨道投影为推理上下文,
                        # 之后 checkpoint 接管
                        incoming = await load_display_history(s, conv_id) + incoming
                    graph_input = {"messages": incoming}

        # 入口守门子图已随旧权限体系移除(2026-08 权限重构);
        # 审批恢复(Command resume)从断点继续、regenerate 从分叉 checkpoint 继续,
        # 落库由 collector 统一接管,无中间态特例

    try:
        if body.get("stream"):  # 如果请求流式输出
            collector = {"text": ""} # 已发 token 累积,流结束落助手消息用

            async def event_stream(): # 异步事件流函数
                aborted = False
                try:
                    async for chunk in run_agent_stream(
                            agent, graph_input, model, config, collector): # 异步流
                        # 前端终止(断开连接)时停止生成,避免空跑烧 token
                        if await request.is_disconnected(): # 如果前端已断开连接
                            aborted = True
                            break # 退出循环
                        yield chunk # 发送当前 chunk
                except Exception:
                    if conv_id:
                        await persist_assistant_message(
                            conv_id, collector["text"], {"error": True})
                    raise
                if conv_id:
                    if aborted:
                        await persist_assistant_message(
                            conv_id, collector["text"], {"aborted": True})
                    else:
                        await persist_assistant_message(conv_id, collector["text"])

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
        if decision:
            return openai_error("审批恢复只支持流式请求(stream=true)", 400)
        payload = await run_agent_non_stream(agent, graph_input["messages"], model, config)
        if conv_id:
            text = payload["choices"][0]["message"].get("content", "")
            await persist_assistant_message(conv_id, text)
        return JSONResponse(content=payload)
    except Exception as e:
        return openai_error(f"Agent 执行失败 [{provider['name']}/{model}]: {e}", 502)


async def _fork_for_regenerate(agent, config: dict, keep: int) -> dict:
    """regenerate:checkpoint 时间旅行分叉 + 展示轨道截断(由 run_agent 调用)。

    keep = 前端 splice(index) 保留的展示消息条数。定位规则:
    截断后剩余 user 消息条数 N → 在 checkpoint 历史(新→旧)中找
    "human 总数 == N 且末尾为 human"的最近快照,用其 checkpoint_id 分叉;
    空输入 {"messages": []} 从该点重跑 agent 节点,精确复刻
    旧版"尾部为空重跑"语义——且真正回到该时点(旧版 checkpoint 仍含
    被删轮次,模型仍记得它们,是隐性 bug)。

    顺序:先定位再截断——定位失败(老历史两轨条数不一致)展示轨道不动;
    截断失败抛异常,图未分叉,两轨不分叉。"""
    conv_id = config["configurable"]["thread_id"]
    async with sessionmaker()() as s:
        n_human = await count_messages(s, conv_id, role="user", before_position=keep)
    target = None
    async for snap in agent.aget_state_history(config):
        msgs = (snap.values or {}).get("messages") or []
        n = sum(1 for m in msgs if getattr(m, "type", "") == "human")
        if n != n_human:
            continue
        if n_human > 0 and (not msgs or getattr(msgs[-1], "type", "") != "human"):
            continue
        target = snap.config["configurable"]["checkpoint_id"]
        break
    if not target:
        raise ValueError("无法定位重新生成的断点(会话历史过久或已被修改)")
    await truncate_display(conv_id, keep)
    return {"configurable": {"thread_id": conv_id, "checkpoint_id": target}}


# ============================================================
# [分支二] 直答转发:无 tools 请求的纯模型调用路径
# ============================================================


async def forward_upstream(request: Request, provider: dict, body: dict, user_id: str):
    """无 tools 请求:用 LangChain ChatOpenAI 调用,输出统一 SSE 事件流。
    直答路径无 checkpoint,推理上下文靠前端全量重发(维持现状);
    展示轨道落库与 Agent 路径同规则:用户消息进调用前落、助手消息流后落"""
    model = body.get("model", "")
    messages = [to_lc_message(m) for m in body.get("messages", [])]
    chat = build_chat(provider, model, body)

    conv_id = body.get("conversation_id")
    if conv_id:
        async with sessionmaker()() as s:
            if not await get_owned_conv(s, conv_id, user_id):
                return openai_error("会话不存在", 404)
        regen = body.get("regenerate") or None
        if regen:
            # 直答模式 regenerate:无 checkpoint 可分叉,只需截断展示轨道,
            # 推理上下文由前端重发的截断后历史提供
            await truncate_display(conv_id, int(regen.get("keep", 0)))
        elif messages and messages[-1].type == "human":
            await persist_user_message(
                conv_id, _message_text(messages[-1]), body.get("attachments"))

    if body.get("stream"):
        async def event_stream():
            collected = ""
            aborted = False
            try:
                async for chunk in chat.astream(messages):
                    # 前端终止(断开连接)时停止生成,避免空跑烧 token
                    if await request.is_disconnected():
                        aborted = True
                        break
                    # 3.3 思考过程流式透传(直答路径)
                    reasoning = getattr(chunk, "additional_kwargs", {}).get("reasoning_content")
                    if reasoning:
                        yield sse_event_bytes("reasoning", {"content": reasoning})
                    content = chunk.content
                    if isinstance(content, str) and content:
                        collected += content
                        yield sse_event_bytes("token", {"content": content})
                    elif isinstance(content, list):
                        for block in content:
                            if block.get("type") == "text":
                                collected += block.get("text", "")
                                yield sse_event_bytes("token", {"content": block.get("text", "")})
            except Exception as e:
                if conv_id:
                    await persist_assistant_message(
                        conv_id, collected or f"请求失败:{e}", {"error": True})
                yield sse_event_bytes("error", {"message": str(e)})
            else:
                if conv_id:
                    if aborted:
                        await persist_assistant_message(
                            conv_id, collected, {"aborted": True})
                    else:
                        await persist_assistant_message(conv_id, collected)
            yield sse_event_bytes("done", {})
            yield b"data: [DONE]\n\n"
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    try:
        resp = await chat.ainvoke(messages)
        answer = resp.content if isinstance(resp.content, str) else "".join(
            b.get("text", "") for b in resp.content if isinstance(b, dict)
        )
        payload = completion_payload(model, answer)
        # 把思考内容透传到响应(原 NestJS 时代由 LangChain 解析 additional_kwargs)
        if hasattr(resp, "additional_kwargs") and resp.additional_kwargs.get("reasoning_content"):
            payload["choices"][0]["message"]["reasoning_content"] = resp.additional_kwargs["reasoning_content"]
        if conv_id:
            await persist_assistant_message(conv_id, answer)
        return JSONResponse(content=mark_content_format(payload))
    except Exception as e:
        return openai_error(f"模型调用失败 [{provider['name']}/{model}]: {e}", 502)


# ============================================================
# [旁路一] 会话与消息 CRUD(会话持久化)
# ============================================================


@app.get("/v1/conversations")
async def list_convs(
    user_id: str = Depends(require_service_key),
    session: AsyncSession = Depends(get_session),
):
    convs = await list_user_convs(session, user_id)
    return {"conversations": [serialize_conv(c, with_messages=False) for c in convs]}


@app.post("/v1/conversations", status_code=201)
async def create_new_conv(
    body: dict | None = None,
    user_id: str = Depends(require_service_key),
    session: AsyncSession = Depends(get_session),
):
    title = (body or {}).get("title", "新对话")
    conv = await create_conv(session, user_id, title)
    return serialize_conv(conv)


@app.get("/v1/conversations/{conv_id}")
async def get_conv(
    conv_id: str,
    user_id: str = Depends(require_service_key),
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.core.db import Conversation
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == user_id,
        ).options(selectinload(Conversation.messages))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "会话不存在")
    return serialize_conv(conv, with_messages=True)


@app.delete("/v1/conversations/{conv_id}")
async def remove_conv(
    conv_id: str,
    user_id: str = Depends(require_service_key),
    session: AsyncSession = Depends(get_session),
):
    ok = await delete_conv(session, user_id, conv_id)
    if not ok:
        raise HTTPException(404, "会话不存在")
    # 联动清理推理轨道:checkpoints.db 里同名 thread 的断点(原为孤儿数据)
    try:
        checkpointer = await get_checkpointer()
        await checkpointer.adelete_thread(conv_id)
    except Exception:
        log.exception("清理 checkpoint 失败 thread=%s(孤儿断点,无正确性影响)", conv_id)
    return {"deleted": conv_id}


@app.post("/v1/conversations/{conv_id}/messages", status_code=201)
async def append_message(
    conv_id: str,
    body: dict,
    user_id: str = Depends(require_service_key),
    session: AsyncSession = Depends(get_session),
):
    """追加一条消息(用户消息或助手消息都可)。
    所有权收敛后前端不再调用(消息由服务端在聊天流程中落库),
    端点保留给第三方/调试用途"""
    conv = await get_owned_conv(session, conv_id, user_id)
    if not conv:
        raise HTTPException(404, "会话不存在")
    msg = await insert_message(
        session, conv_id,
        role=body["role"],
        content=body.get("content", ""),
        attachments=body.get("attachments", []),
        flags=body.get("flags", {}),
    )
    return serialize_msg(msg)


@app.patch("/v1/conversations/{conv_id}")
async def rename_conv(
    conv_id: str,
    body: dict,
    user_id: str = Depends(require_service_key),
    session: AsyncSession = Depends(get_session),
):
    """更新会话标题(首条消息发出后前端自动截取标题)"""
    from sqlalchemy import select
    from app.core.db import Conversation
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == user_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "会话不存在")
    title = (body.get("title") or "").strip()
    if title:
        conv.title = title[:200]
        await session.commit()
    return serialize_conv(conv)


# ============================================================
# [旁路二] 文档与 RAG:上传/检索/重建
# ============================================================


def _parse_text(content: bytes, mime: str, filename: str) -> str:
    """从常见文档格式提取文本(简化版,生产应细分 pdf/docx/xlsx 等)"""
    import io as _io
    text = content.decode("utf-8", errors="replace")
    if "pdf" in mime or filename.lower().endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(_io.BytesIO(content))
            text = "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception:
            pass
    elif "word" in mime or filename.lower().endswith(".docx"):
        try:
            import docx
            d = docx.Document(_io.BytesIO(content))
            text = "\n".join(p.text for p in d.paragraphs)
        except Exception:
            pass
    return text


@app.post("/v1/documents")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Depends(require_service_key),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    """上传文档:保存原文件 + 分块 + Embedding 入库"""
    import io
    content = await file.read()
    text = _parse_text(content, file.content_type or "", file.filename or "unknown")
    if not text.strip():
        raise HTTPException(400, "无法从文档中提取文本")
    embed_model = os.getenv("EMBED_MODEL", "text-embedding-v3")
    provider = PROVIDERS.get(os.getenv("EMBED_PROVIDER", "bailian"))
    if not provider:
        raise HTTPException(500, "未配置嵌入模型来源")
    # Embedding 也走 OpenAI 兼容端点(百炼 / OpenAI 都支持)
    doc_id = await ingest_document(
        session, user_id,
        name=file.filename or "未命名",
        mime_type=file.content_type or "text/plain",
        size=len(content),
        text=text,
        provider=provider,
        embed_model=embed_model,
    )
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    fp = os.path.join(upload_dir, doc_id)
    with open(fp, "wb") as f:
        f.write(content)
    return {"id": doc_id, "name": file.filename, "size": len(content)}


@app.post("/v1/rag/search")
async def rag_search(
    body: dict,
    user_id: str = Depends(require_service_key),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    """检索相关 chunks;后端在生成回答时调用,前端也可直接调"""
    query = body.get("query", "").strip()
    if not query:
        return {"results": []}
    provider = PROVIDERS.get(os.getenv("EMBED_PROVIDER", "bailian"))
    embed_model = os.getenv("EMBED_MODEL", "text-embedding-v3")
    embs = await embed_texts(provider, embed_model, [query])
    results = await search_chunks(session, user_id, embs[0], top_k=body.get("top_k", 5))
    return {"results": results}


@app.post("/v1/documents/rebuild")
async def rebuild_documents(
    user_id: str = Depends(require_service_key),
):
    """按当前检索策略重建索引:全部文档重切 + 重 embedding(策略 A/B 用)。
    流程:读取 uploads 原文件 → 按当前 strategy 重切 → 重 embedding →
    事务内替换 chunks(先删后插)。文档多时应改为后台任务 + 进度查询。"""
    from sqlalchemy import delete, select
    from app.rag.engine import Chunk, chunk_text
    provider = PROVIDERS.get(os.getenv("EMBED_PROVIDER", "bailian"))
    if not provider:
        raise HTTPException(500, "未配置嵌入模型来源")
    embed_model = os.getenv("EMBED_MODEL", "text-embedding-v3")
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    rebuilt, skipped, failed = [], [], []
    async with sessionmaker()() as s:
        docs = (await s.execute(
            select(Document).where(Document.user_id == user_id))).scalars().all()
    for doc in docs:
        fp = os.path.join(upload_dir, doc.id)
        if not os.path.exists(fp):
            skipped.append({"id": doc.id, "name": doc.name, "reason": "原文件缺失"})
            continue
        try:
            with open(fp, "rb") as f:
                content = f.read()
            text = _parse_text(content, doc.mime_type, doc.name)
            pieces = chunk_text(text)  # 按当前策略参数重切
            embeddings = await embed_texts(provider, embed_model, pieces) if pieces else []
            async with sessionmaker()() as s:
                await s.execute(delete(Chunk).where(Chunk.document_id == doc.id))
                import json as _json, uuid as _uuid
                for pos, (piece, emb) in enumerate(zip(pieces, embeddings)):
                    s.add(Chunk(
                        id=_uuid.uuid4().hex, document_id=doc.id,
                        user_id=user_id, position=pos, text=piece,
                        embedding=_json.dumps(emb, ensure_ascii=False)))
                await s.commit()
            rebuilt.append({"id": doc.id, "name": doc.name, "chunks": len(pieces)})
        except Exception as e:
            failed.append({"id": doc.id, "name": doc.name, "error": str(e)})
    from app.contexteng import strategy as cx_strategy
    return {"strategy": cx_strategy.current(), "rebuilt": rebuilt,
            "skipped": skipped, "failed": failed}


# ============================================================
# [旁路三] ASR:语音转文字(百炼 Paraformer 一次性文件识别)
# ============================================================

# 单段音频上限(前端分段录音,每段 ~3s,10MB 绰绰有余)
ASR_MAX_BYTES = 10 * 1024 * 1024


def _asr_recognize(wav_path: str) -> str:
    """同步调用 dashscope Recognition 做一次性文件识别(在线程池里跑)。"""
    import dashscope
    from dashscope.audio.asr import Recognition

    # ASR 走 dashscope SDK 直连(不经 Java 网关),优先 DASHSCOPE_API_KEY
    dashscope.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv(
        "BAILIAN_MODEL_API_KEY", ""
    )
    if not dashscope.api_key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY,无法调用语音识别")
    recognition = Recognition(
        model=os.getenv("ASR_MODEL", "paraformer-realtime-v2"),
        format="wav",
        sample_rate=16000,
        callback=None,
    )
    result = recognition.call(wav_path)
    if result.status_code != 200:
        raise RuntimeError(f"语音识别失败: {result.message}")
    sentences = result.get_sentence() or []
    return "".join(s.get("text", "") for s in sentences).strip()


@app.post("/v1/asr/transcribe")
async def asr_transcribe(
    file: UploadFile = File(...),
    user_id: str = Depends(require_service_key),
):
    """语音转文字:接收 16kHz mono WAV,返回 {"text": "..."}。
    空音频/静音返回空文本,由前端跳过。"""
    import asyncio
    import tempfile

    content = await file.read()
    if not content:
        raise HTTPException(400, "未接收到音频")
    if len(content) > ASR_MAX_BYTES:
        raise HTTPException(413, "音频过大")
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        with tmp:
            tmp.write(content)
        text = await asyncio.get_event_loop().run_in_executor(
            None, _asr_recognize, tmp.name
        )
    finally:
        os.unlink(tmp.name)
    return {"text": text}
