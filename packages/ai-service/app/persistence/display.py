"""展示轨道持久化(会话持久化所有权收敛)。

设计:
- checkpoints.db 是推理轨道的唯一权威;MySQL messages 表是展示轨道的唯一权威;
- 两端写入都在服务端完成,前端只负责带来本轮新消息与展示元数据;
- 常规落库 fail-soft(打日志继续),不影响推理流程;
  regenerate 截断例外——截断失败时两轨会分叉,必须显式报错。
"""
import json
import logging

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import (
    Conversation, Message, count_messages, delete_messages_from,
    insert_message, sessionmaker,
)

log = logging.getLogger(__name__)


async def get_owned_conv(
    session: AsyncSession, conv_id: str, user_id: str
) -> Conversation | None:
    """校验会话存在且归属当前用户"""
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def persist_user_message(
    conv_id: str, content: str, attachments: list | None = None
) -> None:
    """进图前落用户消息(fail-soft)。
    content 为推理用纯文本(前端已把文档文本拼接进来);
    attachments 剥离 text 大字段——文档文本已在 content 中,
    保留会导致老会话回填时二次拼接。"""
    atts = [
        {"type": a.get("type"), "name": a.get("name"), "fileId": a.get("fileId")}
        for a in (attachments or [])
        if isinstance(a, dict)
    ]
    try:
        async with sessionmaker()() as s:
            await insert_message(
                s, conv_id, role="user", content=content, attachments=atts
            )
    except Exception:
        log.exception("用户消息落库失败 conv=%s", conv_id)


async def persist_assistant_message(
    conv_id: str, text: str, flags: dict | None = None
) -> None:
    """流结束(正常/终止/异常)落助手消息(fail-soft)。
    终止且一字未发时补占位文案,与前端本地行为一致;
    空回答且无标志(如纯审批卡片轮次)不落,避免刷新后出现空气泡。"""
    flags = flags or {}
    if flags.get("aborted") and not text:
        text = "已终止回答"
    if not text and not flags:
        return
    try:
        async with sessionmaker()() as s:
            await insert_message(s, conv_id, role="assistant", content=text, flags=flags)
    except Exception:
        log.exception("助手消息落库失败 conv=%s", conv_id)


async def truncate_display(conv_id: str, keep: int) -> int:
    """regenerate:截断展示轨道(position >= keep 删除),
    返回剩余 user 消息条数(供 checkpoint 时间旅行定位)。
    失败抛异常——截断失败而图已分叉会造成两轨分叉,由调用方转 4xx/5xx。"""
    async with sessionmaker()() as s:
        await delete_messages_from(s, conv_id, keep)
        return await count_messages(s, conv_id, role="user")


async def load_display_history(session: AsyncSession, conv_id: str) -> list:
    """老会话一次性回填:messages 表 → LC 消息列表(推理化投影)。
    拼接规则与前端 toOpenAIMessage 一致:
    - 文档附件文本拼进 user 消息(仅老数据;新数据的文档文本已在 content 内);
    - 图片无 url(落库时已剥离)→ 拼占位符"""
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.position)
    )
    out: list = []
    for row in result.scalars():
        text = row.content or ""
        if row.role == "user":
            atts = json.loads(row.attachments or "[]")
            for a in atts:
                if a.get("type") == "file" and a.get("text"):
                    text += f"\n\n【附件文档:{a.get('name')}】\n{a['text']}"
            if any(a.get("type") == "image" for a in atts):
                text += "\n\n(用户此前上传过图片)"
            out.append(HumanMessage(content=text))
        elif row.role == "assistant":
            out.append(AIMessage(content=text))
    return out
