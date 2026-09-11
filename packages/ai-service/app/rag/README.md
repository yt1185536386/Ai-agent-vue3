# rag — RAG 检索子系统

> 文档分块 → Embedding → 向量相似度检索。约 170 行,SQLite 起步、接口预留换向量库。

## 文件地图

| 文件 | 职责 |
|---|---|
| `engine.py` | Document/Chunk 模型(SQLite)+ `chunk_text` 切分 + `embed_texts` 向量化(OpenAI 兼容 /embeddings)+ `search_chunks` 余弦检索 |

## 数据流

```
上传 /v1/documents → _parse_text 抽文本 → chunk_text(策略参数切分)
                  → embed_texts 批量向量化 → chunks 入库
检索:query → embed_texts → search_chunks(top_k)→ threshold 过滤(在 tools/rag.py 做)
```

- 切分/检索参数的唯一来源是 `contexteng/strategy.py`(热切换,支持 A/B)
- 全量重建 `/v1/documents/rebuild`:按新策略重切+重 embedding,事务内先删后插

## 学习路径

1. `engine.py` 自顶向下:两个模型类 → chunk_text → embed_texts → search_chunks
2. 消费方对照:`tools/rag.py`(Agent 工具化,自主决策+事件上报)与 `contexteng/evaluator.py`(离线评测 Recall@K,同口径复用)

## 优化切入点

- **换向量库**:注释已声明 pgvector/Milvus/Chroma 方向,`search_chunks` 签名不变即可替换
- rebuild 是同步执行,文档多会超时 → 后台任务 + 进度查询
- `embed_texts` 每次新建 httpx.AsyncClient → 复用 lifespan 的 `app.state.http`
- 纯向量检索 → 可加 BM25 混合检索提升关键词召回
