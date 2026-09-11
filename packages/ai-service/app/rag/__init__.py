"""RAG 检索子系统:文档分块 + Embedding + 向量相似度检索。

- engine.py  Document/Chunk 模型、chunk_text 切分、embed_texts 向量化、search_chunks 检索

从哪里入手学习:engine.py 自顶向下;检索消费方在 tools/rag.py(Agent 工具化)与
contexteng/evaluator.py(离线评测)。
"""
