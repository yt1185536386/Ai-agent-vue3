"""
会话与消息持久化(SQLAlchemy + async MySQL)。

模型定义保持数据库无关;当前通过 DATABASE_URL 使用 mysql+aiomysql。
"""
import json
import uuid
from datetime import datetime
from typing import AsyncIterator, Optional

from sqlalchemy import (
    String, Text, DateTime, ForeignKey, func, select, delete,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, selectinload,
)


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200), default="新对话")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation",
        cascade="all, delete-orphan", order_by="Message.position",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("conversations.id", ondelete="CASCADE"), index=True,
    )
    # 同一会话内按追加顺序递增,前端排序用
    position: Mapped[int] = mapped_column(index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    # 附件列表(text/image url)JSON 化存储
    attachments: Mapped[str] = mapped_column(Text, default="[]")
    # 错误状态 / 终止状态 / 工具调用中间状态(JSON)
    flags: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


# ---------- 数据库初始化 ----------
_engine = None
_SessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


def init_db(database_url: str) -> None:
    """启动时调用:创建 engine 和表(同步,生命周期内只调一次)"""
    global _engine, _SessionLocal
    _engine = create_async_engine(database_url, echo=False)
    _SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖注入用的 session 生成器"""
    if _SessionLocal is None:
        raise RuntimeError("DB 未初始化,请先调用 init_db()")
    async with _SessionLocal() as session:
        yield session


def sessionmaker() -> async_sessionmaker[AsyncSession]:
    """给非请求场景(如 Agent 工具内部)使用的 session 工厂"""
    if _SessionLocal is None:
        raise RuntimeError("DB 未初始化,请先调用 init_db()")
    return _SessionLocal


async def dispose_db() -> None:
    """释放连接池(脚本类调用方退出前调用,如 eval;
    服务进程随生命周期结束,不需要调)"""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def create_tables() -> None:
    """首次启动建表(开发环境用,生产用 Alembic 迁移)"""
    if _engine is None:
        raise RuntimeError("DB 未初始化")
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------- 业务操作 ----------
def new_conv_id() -> str:
    return uuid.uuid4().hex


async def list_user_convs(session: AsyncSession, user_id: str) -> list[Conversation]:
    result = await session.execute(
        select(Conversation).where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
    )
    return list(result.scalars())


async def create_conv(session: AsyncSession, user_id: str, title: str = "新对话") -> Conversation:
    conv = Conversation(id=new_conv_id(), user_id=user_id, title=title)
    session.add(conv)
    await session.commit()
    # 仅刷新标量字段,避免触发 messages 关系的懒加载
    await session.refresh(conv, attribute_names=["id", "title", "created_at"])
    return conv


async def delete_conv(session: AsyncSession, user_id: str, conv_id: str) -> bool:
    """删除会话(级联清空消息);返回是否存在并删除成功"""
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == user_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return False
    await session.delete(conv)
    await session.commit()
    return True


async def next_position(session: AsyncSession, conv_id: str) -> int:
    """下一条消息的 position:MAX+1。
    不用 count(*):regenerate 截断后会留空洞,count 会复用已删除的序号"""
    pos = (await session.execute(
        select(func.coalesce(func.max(Message.position), -1))
        .where(Message.conversation_id == conv_id)
    )).scalar_one()
    return pos + 1


async def insert_message(
    session: AsyncSession, conv_id: str, *,
    role: str, content: str = "",
    attachments: list | None = None, flags: dict | None = None,
) -> Message:
    """追加一条消息并提交(展示轨道唯一写入入口)"""
    msg = Message(
        conversation_id=conv_id,
        position=await next_position(session, conv_id),
        role=role,
        content=content,
        attachments=json.dumps(attachments or [], ensure_ascii=False),
        flags=json.dumps(flags or {}, ensure_ascii=False),
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def delete_messages_from(session: AsyncSession, conv_id: str, keep: int) -> None:
    """截断展示轨道:删除 position >= keep 的消息(regenerate 用)"""
    await session.execute(
        delete(Message).where(
            Message.conversation_id == conv_id,
            Message.position >= keep,
        )
    )
    await session.commit()


async def count_messages(
    session: AsyncSession, conv_id: str,
    role: str | None = None, before_position: int | None = None,
) -> int:
    """统计会话消息条数(可按 role / position 上限过滤;regenerate 定位用)"""
    stmt = select(func.count(Message.id)).where(Message.conversation_id == conv_id)
    if role is not None:
        stmt = stmt.where(Message.role == role)
    if before_position is not None:
        stmt = stmt.where(Message.position < before_position)
    return (await session.execute(stmt)).scalar_one()


def serialize_msg(m: Message) -> dict:
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "attachments": json.loads(m.attachments or "[]"),
        "flags": json.loads(m.flags or "{}"),
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def serialize_conv(c: Conversation, *, with_messages: bool = False) -> dict:
    """默认不序列化 messages(避免触发懒加载);
    调用方在已 selectinload 时显式传 True"""
    out = {
        "id": c.id,
        "title": c.title,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
    if with_messages:
        out["messages"] = [serialize_msg(m) for m in c.messages]
    return out