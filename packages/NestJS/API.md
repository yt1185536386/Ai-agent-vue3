# Eric Agent 后端服务文档

NestJS 后端，作为前端（Vue3 + LangChain）与 AI 服务层之间的 **网关层**：
统一管理模型来源、注入系统时间、打内容标识、处理附件。
真正的模型调用经 **AI 服务层（FastAPI，`ai-service/`，默认端口 8000）** 转发到模型网关。

- 默认端口：`3000`
- 全部接口前缀：`/v1`
- CORS：已开启（`origin: true`），允许 Vite dev server 等跨域调用
- 请求体上限：50MB（容纳 base64 图片）

**调用链路**：`前端 → NestJS(3000) → FastAPI AI 服务(8000) → 模型网关(公司/百炼)`

---

## 一、目录结构

```
NestJS/
├── .env                     # 环境变量(密钥在此,勿提交)
├── .env.example             # 环境变量模板
├── uploads/                 # 上传附件存储(自动生成,3 天自动清理)
└── src/
    ├── main.ts              # 入口:bodyParser、CORS、端口
    ├── app.module.ts        # 根模块:Config(全局) + Schedule(定时) + Chat + Files
    ├── chat/
    │   ├── chat.module.ts
    │   ├── chat.controller.ts   # /v1 下的模型与会话接口
    │   └── chat.service.ts      # 多来源管理、转发 AI 服务层、能力判断、错误处理
    └── files/
        ├── files.module.ts
        ├── files.controller.ts  # /v1/files 上传/删除
        └── files.service.ts     # 文本提取(pdf/docx/txt)、定时清理

ai-service/                  # AI 服务层(FastAPI + 后续 LangChain Agent)
├── .env                     # 模型密钥(已从 NestJS 下沉到此)
├── requirements.txt
└── app/main.py              # /v1/chat/completions 按 X-Provider 转发上游
```

## 二、环境变量（.env）

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `MODEL_BASE_URL` | 公司模型 OpenAI 兼容地址（不含 /chat/completions） | `http://172.18.200.114:3000/v1` |
| `MODEL_API_KEY` | 公司模型密钥 | `sk-...` |
| `MODEL_NAME` | 公司模型默认模型 | `k3` |
| `MODEL_ENABLE_SEARCH` | 公司网关是否支持联网搜索（`true`/`false`） | `false` |
| `BAILIAN_MODEL_BASE_URL` | 百炼（dashscope 兼容模式）地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `BAILIAN_MODEL_API_KEY` | 百炼密钥 | `sk-...` |
| `BAILIAN_MODEL_NAME` | 百炼默认模型 | `qwen-plus` |
| `BAILIAN_MODEL_ENABLE_SEARCH` | 百炼联网搜索开关（qwen 系列原生支持） | `true` |
| `MODEL_PROVIDER` | 默认来源（`company` / `bailian`） | `company` |
| `VISION_MODELS` | 支持图片的模型（逗号分隔，名称包含匹配，`*` 全部） | `k3,vl` |
| `DOC_MODELS` | 支持文档的模型 | `*` |
| `THINKING_MODELS` | 支持思考模式（enable_thinking）的模型 | `k3,qwen3,deepseek` |
| `PORT` | 服务端口 | `3000` |
| `AI_SERVICE_URL` | AI 服务层（FastAPI）地址，chat completions 经它转发到模型 | `http://localhost:8000` |

> 模型来源/模型的切换是**运行时生效**（内存态），不写回 .env；服务重启后回到 .env 默认值。

## 三、接口一览

### 3.1 模型来源

#### `GET /v1/providers` — 查询所有来源及当前来源

响应：

```json
{
  "providers": [
    { "key": "company", "name": "公司模型" },
    { "key": "bailian", "name": "百炼模型" }
  ],
  "current": "company"
}
```

#### `PUT /v1/providers/current` — 切换来源

请求：

```json
{ "provider": "bailian" }
```

响应（切换后使用该来源的默认模型，前端需重新拉取模型列表）：

```json
{ "current": "bailian", "model": "qwen-plus" }
```

---

### 3.2 模型列表与切换

#### `GET /v1/models` — 当前来源可用模型列表

- 转发上游 `/models`，过滤掉 embedding/语音/图像等非对话模型
- 每个模型附带能力标记

响应：

```json
{
  "data": {
    "data": [
      { "id": "qwen-plus", "capabilities": { "image": false, "doc": true, "thinking": false } }
    ]
  },
  "current": "qwen-plus",
  "capabilities": { "image": false, "doc": true, "thinking": false }
}
```

能力规则（`ChatService.getCapabilities`，按模型名包含匹配）：

| 能力 | 判断来源 | 含义 |
| --- | --- | --- |
| `image` | `VISION_MODELS` | 前端是否允许上传图片 |
| `doc` | `DOC_MODELS` | 前端是否允许上传文档 |
| `thinking` | `THINKING_MODELS` | 前端是否显示「思考」开关 |

#### `PUT /v1/models/current` — 切换当前模型

请求：

```json
{ "model": "deepseek-v4-pro" }
```

响应：

```json
{
  "current": "deepseek-v4-pro",
  "capabilities": { "image": false, "doc": true, "thinking": true }
}
```

---

### 3.3 对话转发

#### `POST /v1/chat/completions` — OpenAI 兼容对话接口

前端 LangChain `ChatOpenAI` 的 baseURL 直接指向本服务，请求体与 OpenAI 完全一致（`messages` / `tools` / `stream` 等）。

**转发时的加工逻辑（`ChatService.chatCompletions`）：**

1. **强制模型**：`model` 字段覆盖为后端当前生效模型（前端传什么都被忽略）
2. **注入系统时间**：在消息列表最前插入 system 消息（网关自带日期不准）：
   `当前真实时间:2026年7月22日 星期三 08:58。回答与日期、时间、最新信息相关的问题时以此为准。`
3. **联网搜索**：当前来源开启搜索时附加 `enable_search: true`
4. **思考模式**：当前模型在 `THINKING_MODELS` 中时透传 `enable_thinking`，否则**剔除**该字段避免上游报错
5. **非流式响应打标**：检测助手回复是否含 Markdown 语法，在消息上写入
   `content_format: "markdown" | "text"`，前端据此决定是否用 Markdown 组件渲染
   （流式 SSE 不打标，前端自行兜底检测）

**流式（`stream: true`）**：SSE 原样透传（`text/event-stream` 逐块转发，不缓冲）。

**错误响应**：统一为 OpenAI 兼容格式（前端 SDK 只认 `error` 字段）：

```json
{
  "error": {
    "message": "内部模型调用失败 [百炼模型/deepseek-v4-flash] HTTP 403: {...}",
    "type": "upstream_error",
    "param": null,
    "code": null
  }
}
```

两类错误的处理：

| 场景 | HTTP 状态 | message 示例 |
| --- | --- | --- |
| 网络层失败（连接拒绝/超时/DNS） | 502 | `模型服务连接失败 [公司模型/k3]: ECONNREFUSED(...)(http://...)` |
| 上游返回错误 | 透传上游状态码 | `内部模型调用失败 [来源/模型] HTTP 403: {上游错误原文}` |

---

### 3.4 附件

#### `POST /v1/files/upload` — 上传图片/文档

- `multipart/form-data`，字段名 `files`，一次最多 10 个，单文件最大 20MB
- 存储到 `./uploads/{uuid}.{ext}`
- 图片仅登记；文档提取文本返回（截断到 8000 字符）

响应（数组，与上传顺序一致）：

```json
[
  {
    "id": "9b1d...uuid.pdf",
    "name": "需求文档.pdf",
    "mimeType": "application/pdf",
    "size": 102400,
    "kind": "doc",
    "text": "提取的文本内容..."
  }
]
```

文本提取支持：

| 类型 | 方式 |
| --- | --- |
| `.txt .md .csv .json .log` | 直接按 UTF-8 读取 |
| `.pdf` | `pdf-parse` |
| `.docx` | `mammoth` |
| 其他 | 返回"暂不支持解析"占位文本 |

#### `POST /v1/files/delete` — 批量删除附件

前端删除会话时联动调用（删除该会话上传过的附件）。

请求：

```json
{ "ids": ["9b1d...uuid.pdf", "..."] }
```

响应：

```json
{ "deleted": 2 }
```

> 有防目录穿越校验（只允许纯文件名）。

**自动清理**：服务启动时 + 每天凌晨 3 点（`@Cron`），删除 mtime 超过 3 天的上传文件。

---

### 3.5 模型来源（已合并到 Java model-gateway `channels` 表）

> **变更**：原 `/v1/admin/models/providers` 增删改接口与 NestJS 自维护的
> `model_providers` 表已废弃（管理端与客户端两套表互不同步，导致管理端新增
> 渠道后客户端查不到）。现在 `channels` 表是唯一数据源：
>
> - **管理端**：ServerManegeUI「渠道管理」→ Java model-gateway `/api/channels`
>   增删改、启停（`status`）。
> - **客户端**：NestJS 运行时只读 `channels` 中 `status=1` 且配置了
>   `channelKey` 的渠道（15s 缓存），作为用户可切换的模型来源；调用经
>   `X-Channel-Key` 头由网关路由到对应渠道，禁用/删除的渠道客户端不可见也不可用。
> - 用户已选来源（`user_chat_settings.provider`）引用 `channelKey`，管理端
>   建渠道时 key 保持一致（如 `company` / `bailian`）即可无缝衔接；存了已停用
>   key 的用户自动回落到优先级最高的启用渠道。
>
> `model_call_logs` 调用日志接口同步废弃：计量/日志统一在网关侧
>（`invoke_logs` + `/api/logs`、`/api/stats`，见 ServerManegeUI 日志看板）。

---

## 四、关键机制速查

```
前端 (Vue3 + LangChain ChatOpenAI)
   │  OpenAI 兼容请求 (baseURL = http://localhost:3000/v1)
   ▼
ChatController ──► ChatService.chatCompletions
   │  ① 覆盖 model  ② 注入时间 system 消息
   │  ③ enable_search(按来源)  ④ enable_thinking(按模型能力,不支持则剔除)
   ▼
FastAPI AI 服务层 (ai-service, :8000,按 X-Provider 选择来源)
   ▼
上游模型网关 (公司网关 / 百炼 dashscope)
   │
   ▼
非流式: 打 content_format 标识后返回 JSON
流式:   SSE 原样透传
错误:   统一 { error: { message } } 格式(AI 服务连接失败 502 / 上游错误透传状态码)
```

- **多来源管理**：来源统一以 Java model-gateway 的 `channels` 表为准，NestJS 运行时只读启用渠道（`status=1` 且配置了 `channelKey`），15s 缓存；用户当前来源/模型存 `user_chat_settings` 表。管理端新增/停用渠道即时（短延迟）影响客户端。
- **调用日志/计量**：已收敛到 Java model-gateway（`invoke_logs` + `/api/logs`、`/api/stats`），本服务不再记录。
- **能力匹配**：`VISION/DOC/THINKING_MODELS` 均为"名称包含匹配"（小写），`*` 表示全部
- **错误提取**：Node fetch 的网络错误从 `error.cause.code` 提取（ECONNREFUSED/ETIMEDOUT 等）
