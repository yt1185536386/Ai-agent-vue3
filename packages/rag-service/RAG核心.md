# RAG 核心流程文档

> 适用代码：`packages/rag-service`（端口 6016）
> 本文档将 rag-service 的三大核心流程（知识库创建、文档入库、知识库问答）完整串联，说明每一步调用哪个模块、为什么需要、数据如何流转。

---

## 0. 系统定位与总览

rag-service 是一个**最小可用的 RAG（检索增强生成）微服务**。它本身不运行任何模型，所有 Embedding 和对话能力都通过内网 `model-gateway`（端口 6015）的 OpenAI 兼容接口完成：

- `POST /v1/embeddings` —— 文本转向量
- `POST /v1/chat/completions` —— 大模型对话
- `GET /v1/channels/{key}` —— 查询渠道模型列表（启动时用）

### 全局架构图

```
用户/前端 (携带 JWT)
    │  /api/rag/**
    ▼
┌────────────────── rag-service (6016) ──────────────────┐
│                                                        │
│  auth   模块 ──→ 校验 JWT + 回库校验用户状态            │
│  kb     模块 ──→ 知识库 CRUD（knowledge_bases 表）      │
│  doc    模块 ──→ PDF 解析 / 切分 / 入库（documents 表） │
│  chat   模块 ──→ 问答流程编排 + 网关客户端              │
│  vector 模块 ──→ 向量存取抽象（内存 / pgvector 双实现） │
│                                                        │
└──────────────────────┬─────────────────────────────────┘
                       │ HTTP（service-key 鉴权 + X-User-Id 计量透传）
                       ▼
               model-gateway (6015)
                       │
                       ▼
              真实的 LLM / Embedding 供应商
```

### 存储双模式

由 `rag.vector.mode` / Spring Profile 控制，业务代码零改动切换：

| 模式 | 激活方式 | 元数据 | 向量 | 适用 |
|---|---|---|---|---|
| memory（默认） | `@Profile("!pgvector")` | H2 内存库 | `ConcurrentHashMap` 暴力 L2 | 本地零依赖开发 |
| pgvector | `-Dspring-boot.run.profiles=pgvector` | PostgreSQL | `document_chunks.embedding vector(1536)` 列，`<->` 算子检索 | 生产 |

### 模块清单速查

| 包 | 关键类 | 职责 | 调用时机 |
|---|---|---|---|
| `auth` | `JwtUtil` | 只校验不签发 JWT（与网关共享 `JWT_SECRET`） | 每个请求 |
| | `AuthInterceptor` | 拦截 `/api/rag/**`：验签 → 回 `users` 表查状态 → 写 AuthContext | 每个请求之前 |
| | `AuthContext` / `CurrentUser` | ThreadLocal 保存当前用户 | 全链路读取 |
| `user` | `UserEntity` / `UserRepository` | 共享 `users` 表的只读映射 | 鉴权回库校验 |
| `kb` | `KnowledgeBaseController/Service` | 知识库 CRUD + `getMine()` 归属校验 | 建库；被 doc/chat 复用 |
| `doc` | `DocumentController/Service` | 文档上传主流程编排（状态机 0/1/-1） | 上传/删除文档 |
| | `PdfParseService` | PDFBox 提取纯文本 | 上传时 |
| | `TextSplitter` | 固定长度+重叠滑动窗口切分（500/100 可配） | 上传时 |
| `vector` | `VectorStore` 接口 | saveChunks / deleteByDocumentId / search | 入库、删除、检索 |
| | `InMemoryVectorStore` / `PgVectorStore` | 双实现 | 按 Profile 二选一 |
| | `pgvector/DocumentChunkRepository` | `ORDER BY embedding <-> :vector LIMIT :topK` | 检索时 |
| `chat` | `RagChatService` | 问答核心编排 | 提问时 |
| | `EmbeddingClient` | 调网关 `/v1/embeddings`（单条+批量） | 入库批量、提问单条 |
| | `ChatClient` | 调网关 `/v1/chat/completions` | 拼完 prompt 后 |
| | `ModelResolver` + `ChannelInfoClient` | 启动时从渠道自动解析 embedding/chat 模型，失败回退硬编码 | `@PostConstruct` |
| `config` | `WebConfig` / `RestClientConfig` / `JpaConfig` | 拦截器注册 / 网关 RestClient / 内存模式排除 pgvector 实体 | 启动装配 |
| `common` | `ApiResponse` / `BizException` / `GlobalExceptionHandler` | 统一响应体与异常处理 | 全链路 |

---

## 1. 流程零：服务启动（一切流程的前置）

```
RagServiceApplication.main
 └─ Spring 容器初始化
     ├─ RestClientConfig  ──→ 构造指向 rag.gateway.base-url 的 RestClient
     │                         （连接超时 5s / 读超时 120s，读超时要容忍 LLM 长生成）
     ├─ ModelResolver.@PostConstruct
     │    ├─ 配置了 rag.model.channel-key
     │    │    └─ ChannelInfoClient GET /v1/channels/{key}
     │    │       → 模型名含 "embedding" 的 → embedding 模型
     │    │       → 含 qwen/gpt/llama/claude 的 → chat 模型
     │    └─ 未配置或解析失败 → 回退 application.yml 硬编码模型
     │       （默认 text-embedding-v3 / qwen-plus，支持 refresh() 热刷新）
     ├─ 按 Profile 激活 InMemoryVectorStore 或 PgVectorStore
     ├─ JPA 自动建表（ddl-auto: update）
     │    memory 模式：JpaConfig 限定扫描包，排除 pgvector 实体
     │    pgvector 模式：需先执行 init.sql → CREATE EXTENSION vector
     └─ WebConfig 挂载 AuthInterceptor 到 /api/rag/**，放开 CORS
```

**为什么需要 ModelResolver**：模型名不该硬编码在业务代码里。渠道在 model-gateway 侧调整模型列表后，rag-service 调用 `refresh()` 即可跟随，无需重启改配置。

---

## 2. 流程一：创建知识库（RAG 检索范围的建立）

```
POST /api/rag/kbs
Headers: Authorization: Bearer <JWT>
Body:    {"name": "产品手册", "description": "公司产品的 PDF 手册"}
```

```
请求进入
 → AuthInterceptor.preHandle                          [auth]
 │   1. 取 Bearer Token，缺失 → 401
 │   2. JwtUtil.parse 验签，失败 → 401
 │   3. userRepository.findById(sub) 回 users 表
 │      ├─ 找到且 status=1 → AuthContext.set(CurrentUser)
 │      ├─ 找到但 status≠1 → 403 "账号已被禁用"（禁用立即生效）
 │      └─ 没找到 → 降级为仅 JWT 声明校验（未共享 users 表场景）
 → KnowledgeBaseController.create                      [kb]
 → KnowledgeBaseService.create
 │   ownerUserId = AuthContext.require().userId()
 │   → 插入 knowledge_bases 表
 ← ApiResponse { errCode:"0", data:{ id, name, ... } }
请求结束 → AuthInterceptor.afterCompletion → AuthContext.clear()
```

**关键设计**：`ownerUserId` 在创建时绑定当前用户，之后所有对该库的操作（传文档、问答、删除）都先过 `KnowledgeBaseService.getMine()` 做归属校验——**知识库是多租户隔离的边界**。

---

## 3. 流程二：上传 PDF 入库（RAG 的"写"路径）

```
POST /api/rag/kbs/{kbId}/documents
Headers: Authorization: Bearer <JWT>
Body:    multipart/form-data, file=@manual.pdf
```

```
请求进入
 → AuthInterceptor 鉴权（同流程一）
 → DocumentController.upload
 → DocumentService.upload（@Transactional）
 │
 │  ① kbService.getMine(kbId)                    [kb]
 │     └─ 归属校验：别人的库 → 400 "无权限访问该知识库"
 │
 │  ② 插入 documents 记录，status=0（解析中）      [doc]
 │     └─ 先落库再处理：即使后续失败也有记录可查
 │
 │  ③ PdfParseService.extractText(file)          [doc]
 │     ├─ 非 .pdf → 400；PDFBox Loader.loadPDF
 │     ├─ PDFTextStripper(sortByPosition=true) 抽文本
 │     └─ normalize: 合并多余空白、统一换行
 │
 │  ④ TextSplitter.split(text, 500, 100)         [doc]
 │     ├─ 固定长度 500 字 + 重叠 100 字滑动窗口
 │     ├─ 为什么重叠：跨块边界的句子不被拦腰截断，语义连续
 │     └─ 切不出有效块 → 400
 │
 │  ⑤ EmbeddingClient.embedBatch(chunks, uid, name) [chat→gateway]
 │     ├─ POST /v1/embeddings
 │     │    Auth: Bearer {service-key}（服务间密钥）
 │     │    Header: X-User-Id / X-Username（真实用户透传，网关计量）
 │     │    Body: { model: ModelResolver 解析的 embedding 模型, input: [...] }
 │     ├─ 响应 data[i].embedding → float[]
 │     └─ 数量与 chunks 不一致 → 400
 │
 │  ⑥ VectorStore.saveChunks(docId, kbId, chunks)   [vector]
 │     ├─ memory:  ChunkData 列表存 ConcurrentHashMap
 │     └─ pgvector: DocumentChunkEntity 批量入库
 │         （VectorConverter 把 float[] 转成 PGvector 写入 vector(1536) 列）
 │
 │  ⑦ documents.status=1（已解析），返回文档信息
 │
 └─ 任一步骤抛异常 → catch：status=-1 + errorMessage，继续抛出
    → GlobalExceptionHandler 包装成 ApiResponse 返回
```

**为什么用状态机（0 解析中 / 1 成功 / -1 失败）**：入库是多步骤外部调用（解析、Embedding 都可能失败），用户需要能区分"还在处理"和"挂了、为什么挂"，而不是干等或看到泛化的 500。

**删除文档**：

```
DELETE /api/rag/kbs/{kbId}/documents/{docId}
 → 归属校验 → vectorStore.deleteByDocumentId(docId)（删向量/chunks）
 → documentRepository.delete（删元数据）
```

---

## 4. 流程三：知识库问答（RAG 的"读"路径，核心闭环）

```
POST /api/rag/kbs/{kbId}/chat
Headers: Authorization: Bearer <JWT>
Body:    {"question": "这款产品支持哪些模型？"}
```

```
请求进入
 → AuthInterceptor 鉴权（同流程一）
 → RagChatController.chat
 → RagChatService.ask(kbId, question)
 │
 │  ① kbService.getMine(kbId)                    [kb]
 │     └─ 归属校验（任何问答前先确认是自己的库）
 │
 │  ② EmbeddingClient.embed(question, uid, name) [chat→gateway]
 │     └─ POST /v1/embeddings → 问题 → 1536 维向量
 │
 │  ③ VectorStore.search(kbId, questionVector, topK=5)  [vector]
 │     ├─ memory:  全量扫描该 kbId 的 chunks，算 L2 距离排序取前 5
 │     └─ pgvector: SELECT * FROM document_chunks
 │                  WHERE knowledge_base_id = :kbId
 │                  ORDER BY embedding <-> :vector LIMIT 5
 │     └─ 命中 0 条 → 直接返回 "知识库中暂无相关文档，无法回答问题。"
 │
 │  ④ 拼接上下文 + system prompt                  [chat]
 │     """
 │     你是一个严谨的智能助手。请严格根据以下上下文回答用户问题。
 │     如果上下文不足以回答问题，请明确说明"根据提供的资料无法回答"。
 │     不要编造上下文之外的信息。
 │     上下文：
 │     {chunk1}
 │     ---
 │     {chunk2} ...
 │     """
 │     messages = [system(上下文), user(原始问题)]
 │     └─ 为什么这样写 prompt：用指令压制幻觉，让模型"没资料就承认"
 │
 │  ⑤ ChatClient.chat(messages, uid, name)       [chat→gateway]
 │     ├─ POST /v1/chat/completions（OpenAI 兼容，非流式）
 │     ├─ model = ModelResolver 解析的 chat 模型
 │     └─ 取 choices[0].message.content 作为答案
 │
 │  ⑥ 组装响应
 │     └─ ChatResponse { answer, references: ["[片段 0] ...", "[片段 3] ..."] }
 │        references 即检索命中的原文片段，供前端展示引用来源
 ← ApiResponse { errCode:"0", data:{ answer, references } }
```

### 一次问答的时序全图

```
前端          rag-service            model-gateway          供应商
 │                │                      │                    │
 │── JWT+问题 ───▶│                      │                    │
 │                │── 验签/查用户 ─┐      │                    │
 │                │◀─────────────┘      │                    │
 │                │── embed(问题) ─────▶│── embedding ──────▶│
 │                │◀── 1536 维向量 ─────│◀───────────────────│
 │                │── 向量库 Top-5 ─┐   │                    │
 │                │◀───────────────┘   │                    │
 │                │── chat(上下文+问题)▶│── chat 模型 ───────▶│
 │                │◀── 答案文本 ────────│◀───────────────────│
 │◀─ answer+引用 ─│                      │                    │
```

---

## 5. 三条流程的串联关系

```
                    ┌─────────────────────────────┐
                    │   AuthInterceptor（公共前置） │
                    │   JWT 验签 + 用户状态回库校验 │
                    └──────────────┬──────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
  流程一：建库                 流程二：入库                 流程三：问答
  POST /kbs                  POST /kbs/{id}/documents    POST /kbs/{id}/chat
        │                          │                          │
        │                     getMine(kbId) ◀─────────────────┤ 共用归属校验
        │                          │                          │
        ▼                          ▼                          ▼
  knowledge_bases            documents(状态机)            embed(问题)
  写入 ownerUserId           + PdfParse                     │
        ▲                    + TextSplitter                 ▼
        │                    + embedBatch ──────▶   VectorStore.search
        │                          │                  （读 chunks）
        │                          ▼                          │
        │                  VectorStore.saveChunks             ▼
        │                  （写 chunks）              拼 prompt → chat
        │                          │                          │
        └──────────────────────────┴──────────────────────────┘
                          数据纽带：kbId
            knowledge_bases ─1:N─ documents ─1:N─ document_chunks
```

**串联要点**：

1. **auth 是所有流程的统一入口**：JWT 身份 → ThreadLocal → 业务层随处可取，且用户禁用立即生效。
2. **kbId 是数据隔离的纽带**：建库绑定 owner，入库和检索都限定在同一个 kbId 内。
3. **ModelResolver 贯穿写读两条路径**：入库的批量 Embedding 和问答的单条 Embedding / Chat 使用同一套模型解析结果，保证"写入向量"和"查询向量"来自同一模型（维度、语义空间一致——这是 RAG 正确性的硬前提）。
4. **计量归因链完整**：用户 JWT → AuthContext → `X-User-Id` 透传 → 网关按真实用户计量，rag-service 自身用 service-key 认证。
5. **VectorStore 抽象是读写路径的唯一交汇点**：写路径 saveChunks，读路径 search，删除路径 deleteByDocumentId，底层实现可整体替换。

---

## 6. 已知限制与改进方向

| 现状 | 影响 | 改进方向 |
|---|---|---|
| 删除知识库不级联清理 documents / document_chunks | 孤儿数据 | delete 时级联删除 |
| ChatClient 非流式 | 长回答等待感强 | 改 SSE 流式透传 |
| `pageCount` 硬编码为 1 | 文档信息不准 | 用 PDDocument.getNumberOfPages() |
| InMemory 检索全量扫描 O(N) | 仅适合开发 | 生产必须 pgvector |
| Chunk Size / Top-K 等参数靠经验值 | 优化无依据 | 建评估体系（测试集 + HitRate@K + faithfulness + 延迟） |
| 检索只有向量相似度，无重排/混合检索 | 召回质量受限 | 加 rerank、关键词+向量混合检索 |
