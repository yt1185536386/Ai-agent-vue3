"""
RAG 检索:文档分块 + Embedding + 简单向量相似度。

学习阶段用 SQLite 存储 chunks(内容 + embedding 序列化);
后续可替换为 pgvector/Milvus/Chroma,接口保持不变。

Embedding: 复用对话来源的 baseURL 与 key,使用 OpenAI 兼容接口的 /embeddings 端点。
"""
import json
import math
import re
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Document(Base): 
    """用户上传的文档(元数据)"""
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(120))
    size: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Chunk(Base):
    """文档块 + 序列化后的 embedding 字符串(列表 JSON)"""
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    position: Mapped[int] = mapped_column()
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[str] = mapped_column(Text)  # JSON 序列化的浮点数列表


# ---------- 分块 ----------
def chunk_text(text: str, *, size: int | None = None, overlap: int | None = None) -> list[str]:
    """简单按字符数切块(中英文通用),保留 overlap 以提升上下文连贯。
    生产可替换为按段落/语义/句切分。
    size/overlap 缺省时从检索策略对象读取(contexteng.strategy,可热调)。"""
    if size is None or overlap is None:
        from app.contexteng import strategy as cx_strategy
        cfg = cx_strategy.current()
        size = size if size is not None else cfg["size"]
        overlap = overlap if overlap is not None else cfg["overlap"]
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    i = 0
    while i < len(text):
        piece = text[i : i + size]
        chunks.append(piece)
        if i + size >= len(text):
            break
        i += size - overlap
    return chunks


# ---------- Embedding ----------
async def embed_texts(provider: dict, model: str, texts: list[str]) -> list[list[float]]:
    """调用 OpenAI 兼容 /embeddings 端点批量向量化"""
    import httpx
    headers = {}
    if provider.get("api_key"):
        headers["Authorization"] = f"Bearer {provider['api_key']}"
    if provider.get("key"):
        # Java 模型网关按渠道 key 路由
        headers["X-Channel-Key"] = provider["key"]
    if provider.get("user_id"):
        headers["X-User-Id"] = provider["user_id"]
    if provider.get("username"):
        headers["X-Username"] = provider["username"]
    if provider.get("request_id"):
        # 全链路请求 ID 透传,Java 网关落 invoke_logs 供排障关联
        headers["X-Request-Id"] = provider["request_id"]
    async with httpx.AsyncClient(base_url=provider["base_url"], headers=headers, timeout=60.0) as c:
        resp = await c.post("/embeddings", json={"model": model, "input": texts})
    if resp.status_code != 200:
        raise RuntimeError(f"Embedding 失败 {resp.status_code}: {resp.text}")
    data = resp.json()
    return [d["embedding"] for d in data["data"]]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


async def search_chunks(
    session: AsyncSession,
    user_id: str,
    query_embedding: list[float],
    *,
    top_k: int | None = None,
) -> list[dict]:
    """检索当前用户最相似的 chunks(线性扫描;学习阶段够用,
    数据量大后换 pgvector <-> 运算符)。
    top_k 缺省时从检索策略对象读取;结果带 chunk_id/position,
    供检索事件(cx_retrieval_events.hits)记录与召回归因。"""
    if top_k is None:
        from app.contexteng import strategy as cx_strategy
        top_k = cx_strategy.current()["top_k"]
    result = await session.execute(
        select(Chunk).where(Chunk.user_id == user_id)
    )
    scored = []
    for c in result.scalars():
        emb = json.loads(c.embedding)
        scored.append({
            "chunk_id": c.id,
            "doc_id": c.document_id,
            "position": c.position,
            "text": c.text,
            "doc": c.document_id,  # 兼容旧调用方(main.py /v1/rag/search)
            "score": cosine(query_embedding, emb),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


async def ingest_document(
    session: AsyncSession,
    user_id: str,
    name: str,
    mime_type: str,
    size: int,
    text: str,
    provider: dict,
    embed_model: str,
) -> str:
    """切块 → 向量化 → 入库;返回 document_id"""
    pieces = chunk_text(text)
    if not pieces:
        # 文本为空时仍建一个 doc 记录,但不建 chunks
        doc_id = uuid.uuid4().hex
        session.add(Document(id=doc_id, user_id=user_id, name=name, mime_type=mime_type, size=size))
        await session.commit()
        return doc_id

    embeddings = await embed_texts(provider, embed_model, pieces)
    doc_id = uuid.uuid4().hex # 文档 ID
    session.add(Document(id=doc_id, user_id=user_id, name=name, mime_type=mime_type, size=size)) # 文档元数据
    for pos, (piece, emb) in enumerate(zip(pieces, embeddings)): # 文档块
        session.add(Chunk(
            id=uuid.uuid4().hex,
            document_id=doc_id,
            user_id=user_id,
            position=pos,
            text=piece,
            embedding=json.dumps(emb, ensure_ascii=False),
        )) # 文档块 入库
    await session.commit() # 提交事务
    return doc_id