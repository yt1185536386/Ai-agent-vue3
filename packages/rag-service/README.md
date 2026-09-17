# rag-service

基于 `model-gateway` 的 `/v1/embeddings` 与 `/v1/chat/completions` 实现的最小可用 RAG 服务。

## 能力

- 创建知识库
- 上传 PDF → 解析文本 → 切分 → Embedding → 存入 `pgvector`
- 对知识库提问：Embed 问题 → 向量检索 Top-K → 拼 Prompt → 调用大模型 → 返回答案

## 快速启动

### 1. 启动 PostgreSQL + pgvector

```powershell
cd packages/rag-service
docker-compose up -d
```

### 2. 启动 model-gateway

确保 `model-gateway` 已配置 embedding 模型（如 `text-embedding-3-small`）与 chat 模型（如 `gpt-4o-mini`）的渠道。

```powershell
cd packages/model-gateway
mvn spring-boot:run
```

### 3. 配置并启动 rag-service

默认读取环境变量，也可直接修改 `application.yml`：

```powershell
$env:JWT_SECRET = "model-gateway-dev-secret-key-please-change-in-prod"
$env:GATEWAY_SERVICE_KEY = "your-service-key"
mvn spring-boot:run
```

## 测试流程

1. 从 NestJS 网关或 model-gateway seed 账号获取 JWT（需与 `JWT_SECRET` 一致）。

2. 创建知识库

```bash
curl -X POST http://localhost:26016/api/rag/kbs \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"name":"产品手册","description":"公司产品的 PDF 手册"}'
```

3. 上传 PDF

```bash
curl -X POST "http://localhost:26016/api/rag/kbs/<kbId>/documents" \
  -H "Authorization: Bearer <JWT>" \
  -F "file=@manual.pdf"
```

4. 问答

```bash
curl -X POST "http://localhost:26016/api/rag/kbs/<kbId>/chat" \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"question":"这款产品支持哪些模型？"}'
```

## 配置说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `server.port` | 26016 | 服务端口 |
| `spring.datasource.url` | `jdbc:postgresql://localhost:5433/rag_db` | PostgreSQL 地址 |
| `rag.jwt.secret` | 与 gateway 同默认值 | JWT 共享密钥 |
| `rag.gateway.base-url` | `http://localhost:26015` | model-gateway 地址 |
| `rag.gateway.service-key` | 空 | 内部服务密钥 |
| `rag.model.embedding-model` | `text-embedding-3-small` | embedding 模型 |
| `rag.model.chat-model` | `gpt-4o-mini` | 对话模型 |
| `rag.retrieval.top-k` | 5 | 检索 chunk 数量 |
| `rag.chunk.size` | 500 | 切分长度 |
| `rag.chunk.overlap` | 100 | 切分重叠 |
| `rag.vector.dimension` | 1536 | 向量维度 |

## 注意

- `document_chunks.embedding` 列默认维度为 1536。若使用其他 embedding 模型，请同步调整 `VECTOR_DIMENSION` 并在首次启动前确保 PostgreSQL 中该列为对应维度。
- 当 rag-service 与 model-gateway/NestJS 共用 `users` 表时，JWT 拦截器会回库校验用户状态；未共享时则退化为仅校验 JWT 签名。
