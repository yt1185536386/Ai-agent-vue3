"""RAG 检索工具(闭包注入用户与 embedding 配置):
把「是否查文档」从强制注入改为 Agent 自主决策。

检索参数(top_k / threshold)从检索策略对象读取(contexteng.strategy,
API 可热调);每次调用向 contexteng.collector 上报检索事件(失败静默)。
工具描述支持 DB 模板('rag.search_docs')覆盖,激活新模板即调优工具提示。
"""
import time

from langchain_core.tools import tool

# 代码内默认工具描述(DB 无模板时使用)
_DEFAULT_DOC = """当用户的问题可能涉及其上传过的文档资料时调用,
传入检索关键词,返回最相关的文档片段。
闲聊、常识问题、与文档无关的问题不要调用。"""


def build_rag_tool(user_id: str, embed_provider: dict, embed_model: str):
    from app.core.db import sessionmaker # 引入异步会话工厂
    from app.rag.engine import embed_texts, search_chunks # 引入异步函数

    @tool
    async def search_docs(query: str) -> str:
        """当用户的问题可能涉及其上传过的文档资料时调用,
        传入检索关键词,返回最相关的文档片段。
        闲聊、常识问题、与文档无关的问题不要调用。"""
        from app.contexteng import collector, strategy as cx_strategy
        cfg = cx_strategy.current() # 检索策略(热读,支持调参实验)
        t0 = time.perf_counter()
        embs = await embed_texts(embed_provider, embed_model, [query]) # 向量化查询
        async with sessionmaker()() as s: # 异步会话
            hits = await search_chunks(s, user_id, embs[0], top_k=cfg["top_k"]) # 检索最相似的 chunks
        latency_ms = int((time.perf_counter() - t0) * 1000)
        # 候选最高分(过滤前):零结果时也要记录,便于分析阈值合理性
        candidate_max = hits[0]["score"] if hits else 0.0
        hits = [h for h in hits if h.get("score", 0) > cfg["threshold"]] # 过滤相似度高 chunks
        collector.report_retrieval({ # 检索事件上报(后台落库,失败静默)
            "user_id": user_id,
            "query": query,
            "strategy": cfg["strategy"],
            "top_k": cfg["top_k"],
            "threshold": cfg["threshold"],
            "hits": [{"chunk_id": h["chunk_id"], "doc_id": h["doc_id"],
                      "score": round(h["score"], 4), "position": h["position"]}
                     for h in hits],
            "hit_count": len(hits),
            "max_score": round(hits[0]["score"], 4) if hits else round(candidate_max, 4),
            "latency_ms": latency_ms,
        })
        if not hits: # 如果没有相似度高的 chunks
            return "未在用户文档中找到相关内容,请基于自身知识回答并说明文档中没有相关信息"
        return "\n\n---\n\n".join(h["text"] for h in hits)

    # DB 模板激活时用模板文本覆盖工具描述(模板调优直接改变模型行为)
    try:
        from app.prompteng.service import load_content
        custom = load_content("rag.search_docs")
        if custom:
            search_docs.description = custom
    except Exception:
        pass  # 模板读取失败静默,用代码默认描述

    return search_docs
