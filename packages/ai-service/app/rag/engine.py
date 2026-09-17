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


# ---------- 混合检索:BM25(稀疏关键词) + 向量余弦(语义),RRF 融合 ----------
# 轻量 BM25Okapi,无第三方依赖;文档量小(SQLite 学习版),每次检索现建索引。
# 引入动机:纯向量余弦对"精确标识符"(合同号/人名/型号等)召回差,BM25 补足关键词命中。
_BM25_K1 = 1.5   # BM25 词频饱和参数
_BM25_B = 0.75   # BM25 文档长度归一
_RRF_K = 60      # RRF 常数 k(标准值 60,用于"排名倒数之和"融合)


def _tokenize(text: str) -> list[str]:
    """基础词元化:英文单词/数字 + 中文单字(不依赖分词库,学习版够用)。"""
    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text.lower())


def _bm25_scores(query_tokens: list[str], doc_tokens: list[list[str]]) -> list[float]:
    """对给定 query 计算每个文档的 BM25Okapi 分。
    若 query 与任一文档都无共享词则返回空列表,调用方据此退化为纯余弦。"""
    n = len(doc_tokens)
    if n == 0:
        return []
    avgdl = sum(len(d) for d in doc_tokens) / n
    df: dict = {}
    for d in doc_tokens:
        for w in set(d):
            df[w] = df.get(w, 0) + 1
    idf = {w: math.log((n - df[w] + 0.5) / (df[w] + 0.5) + 1) for w in df}
    if not any(w in idf for w in set(query_tokens)):
        return []  # 无关键词交集 → 触发退化
    scores = []
    for d in doc_tokens:
        dl = len(d)
        if dl == 0:
            scores.append(0.0)
            continue
        tf: dict = {}
        for w in d:
            tf[w] = tf.get(w, 0) + 1
        s = 0.0
        for w in set(query_tokens):
            f = tf.get(w)
            if f:
                denom = f + _BM25_K1 * (1 - _BM25_B + _BM25_B * dl / avgdl)
                s += (idf.get(w, 0) * f * (_BM25_K1 + 1)) / denom
        scores.append(s)
    return scores


def _rrf_mix(cosine_order: list[tuple[int, float]],
             bm25_order: list[tuple[int, float]],
             top_k: int) -> dict[int, dict]:
    """RRF(Reciprocal Rank Fusion)融合两路排序,返回 RRF 排序的
    {pos: {cosine, bm25, rrf}}。pos 为行下标(与返回 rows 对齐)。"""
    rrf: dict[int, float] = {}
    for rank, (pos, _) in enumerate(cosine_order):
        rrf[pos] = rrf.get(pos, 0.0) + 1.0 / (_RRF_K + rank + 1)
    for rank, (pos, _) in enumerate(bm25_order):
        rrf[pos] = rrf.get(pos, 0.0) + 1.0 / (_RRF_K + rank + 1)
    merged = {pos: {"rrf": rrf[pos]}
              for pos in sorted(rrf, key=rrf.get, reverse=True)[:top_k]}
    cos = dict(cosine_order)
    b25 = dict(bm25_order)
    for pos in merged:
        merged[pos]["cosine"] = cos.get(pos, 0.0)
        merged[pos]["bm25"] = b25.get(pos, 0.0)
    return merged


async def search_chunks(
    session: AsyncSession,
    user_id: str,
    query_embedding: list[float],
    *,
    query: str,
    top_k: int | None = None,
) -> list[dict]:
    """混合检索:余弦(语义) + BM25(关键词) 双路召回,RRF 融合排序后取 top_k。

    - 语义:query_embedding 余弦相似度(原实现,保留);
    - 关键词:由 query 原文走轻量 BM25Okapi(无依赖),补足纯向量易漏的
      精确标识符(合同号/人名等)召回;
    - 融合:RRF 取两路排名倒数之和,兼顾"语义相近"与"关键词命中";
      query 与文档无关键词交集时退化为纯余弦(与旧行为一致)。

    返回按 RRF 排序;每条含 score(余弦,保持旧 threshold 语义)、bm25、rrf。
    top_k 缺省从检索策略读取;chunk_id/position 供检索事件与召回归因。"""
    if top_k is None:
        from app.contexteng import strategy as cx_strategy
        top_k = cx_strategy.current()["top_k"]
    result = await session.execute(
        select(Chunk).where(Chunk.user_id == user_id)
    )
    rows = result.scalars().all()
    if not rows:
        return []

    qtokens = _tokenize(query)
    docs_tokens: list[list[str]] = []
    cosine_order: list[tuple[int, float]] = []
    for pos, c in enumerate(rows):
        emb = json.loads(c.embedding)
        cosine_order.append((pos, cosine(query_embedding, emb)))
        docs_tokens.append(_tokenize(c.text))

    bm25_scores = _bm25_scores(qtokens, docs_tokens)
    if bm25_scores:
        bm25_order = list(enumerate(bm25_scores))
        merged = _rrf_mix(
            sorted(cosine_order, key=lambda t: t[1], reverse=True),
            sorted(bm25_order, key=lambda t: t[1], reverse=True),
            top_k,
        )
    else:
        # 无关键词交集 → 纯余弦(df:有序字典,按 score 降序插入)
        merged = {pos: {"cosine": score, "bm25": 0.0, "rrf": 0.0}
                  for pos, score in
                  sorted(cosine_order, key=lambda t: t[1], reverse=True)[:top_k]}

    return [
        {
            "chunk_id": rows[pos].id,
            "doc_id": rows[pos].document_id,
            "position": rows[pos].position,
            "text": rows[pos].text,
            "doc": rows[pos].document_id,  # 兼容旧调用方(main.py /v1/rag/search)
            "score": round(merged[pos]["cosine"], 4),
            "bm25": round(merged[pos]["bm25"], 4),  # 关键词分值(新增)
            "rrf": round(merged[pos]["rrf"], 6),    # 融合分(新增)
        }
        for pos in merged
    ]


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