# Agent 学习路线

> 针对 `v3agent` 项目（Vue3 + NestJS + FastAPI + LangGraph）的系统性学习路径。
> 项目当前状态：已有较完整的端到端 Agent 能力，进入理解与优化阶段。

---

## 第一阶段：建立全局认知（1-2 天）

**目标**：知道一个请求从发出去到回来，经历了哪些模块。

### 1. 阅读架构文档

- 读 `项目架构说明.md`
- 重点理解三层架构：
  - **前端**：Vue3 + SSE 流式消费
  - **网关**：NestJS 鉴权 / 路由 / 模型管理 / 文件上传
  - **AI 服务**：FastAPI + LangGraph ReAct Agent

### 2. 按顺序走一遍接口

启动 NestJS、FastAPI、Vue3 后，打开浏览器 F12 → Network 面板，发一条消息，观察：

- `GET /v1/providers`：模型来源列表
- `GET /v1/models`：当前来源下的模型列表
- `POST /v1/chat/completions`：流式对话请求
- 可选 `POST /v1/files/upload`：附件上传

### 3. 对照代码看链路

- **前端**：`my-vue-app-ts/src/view/AgentMode/mixin.ts`
  - `runAgent`：怎么构造请求体
  - `parseSSE`：怎么把字节流解析成事件帧
- **网关**：`NestJS/src/chat/`
  - `chat.controller.ts`：怎么透传请求
  - `chat.service.ts`：怎么管理 provider 和模型能力
- **AI 服务**：`ai-service/app/`
  - `main.py`：`/v1/chat/completions` 入口
  - `agent.py`：ReAct 循环与 SSE 事件产出

**输出物**：能手画一张三层调用图。

---

## 第二阶段：读懂 Agent 核心（2-3 天）

**目标**：理解 ReAct Agent 是怎么思考的，工具是怎么被调用的。

### 1. 从入口开始读 `ai-service/app/agent.py`

需要理解的几个点：

- **工具定义**：`get_weather` 是怎么注册的？tool schema 长什么样？
- **ReAct 构建**：`create_react_agent` 怎么把 LLM + tools + prompt 拼起来
- **事件封装**：`token` / `tool_start` / `tool_end` / `done` / `error` 这些 SSE 事件是怎么产出的
- **思考模式与联网**：`enable_thinking` / `enable_search` 怎么影响请求参数

### 2. 读 `ai-service/app/main.py`

- 没有 tools 时，怎么直接走 OpenAI 兼容转发？
- 有 tools 时，怎么进入 Agent 路径？
- 请求体里的 `messages` 是怎么传给 `agent.py` 的？

### 3. 读前端事件消费

`my-vue-app-ts/src/view/AgentMode/mixin.ts` 中：

- `parseSSE`：把流切分成事件帧
- `runAgent` 中的 `switch (event)`：
  - `token`：追加文本
  - `tool_start`：显示"正在调用工具"
  - `tool_end`：隐藏工具提示
  - `done` / `error`：结束或报错

**输出物**：能手动画出一次 ReAct 循环；能说清楚每个 SSE 事件在前端怎么处理。

---

## 第三阶段：动手改造小功能（3-5 天）

**目标**：通过改代码加深理解，从"看懂"到"能改"。

### 推荐练习

1. **加一个新工具**
   - 在 `agent.py` 里加一个 `get_time` 或 `calculate` 工具
   - 前端会自然显示 `tool_start` / `tool_end`

2. **让工具调用结果可视化**
   - 现在 `tool_start` 只显示"正在调用工具"
   - 改成显示工具名、参数、执行结果

3. **会话持久化**
   - 前端会话目前存在 `localStorage`
   - 尝试对接后端 `/v1/conversations`（FastAPI 已存表）

4. **Agent 状态机显示**
   - 在聊天界面显示当前状态：思考中 / 调用工具中 / 生成回复中

5. **支持中断 Agent 思考**
   - 当前 `stopAgent` 只能终止前端 fetch
   - 尝试让后端也支持停止（如检查 Abort Signal）

**输出物**：至少提交一个 commit，完成一个端到端小改造。

---

## 第四阶段：往深里走

1. **LangGraph 官方文档**
   - 理解 graph、node、edge、state、checkpointer

2. **多 Agent 协作**
   - 把单一 ReAct 扩展成：规划 Agent + 执行 Agent + 总结 Agent

3. **RAG 增强**
   - 从现在的线性余弦相似度，升级到 pgvector 或 Milvus

4. **观测性**
   - 加入日志 trace、token 用量统计、慢请求告警

5. **测试与部署**
   - 补单元测试
   - Docker / docker-compose 一键部署
   - CI/CD 流水线

---

## 建议学习顺序

| 天数  | 学习内容                       | 输出物                     |
| ----- | ------------------------------ | -------------------------- |
| 1     | 启动项目 + 走接口 + 读架构文档 | 能画出三层调用图           |
| 2-3   | 精读 `agent.py` + `main.py`    | 能手动画出 ReAct 循环      |
| 4-5   | 精读前端 `mixin.ts` SSE 部分   | 能说清楚每个 event 怎么处理 |
| 6-8   | 加一个小工具 / 改 UI 展示      | 提交一个 commit            |
| 9-12  | 会话持久化或 RAG 升级          | 完成一个端到端改造         |

---

## 快速索引

- 前端 Agent 视图：`my-vue-app-ts/src/view/AgentMode/`
- 网关 chat 模块：`NestJS/src/chat/`
- AI 服务主入口：`ai-service/app/main.py`
- AI 服务 Agent 核心：`ai-service/app/agent.py`
- AI 服务数据库模型：`ai-service/app/db.py`
- AI 服务 RAG 模块：`ai-service/app/rag.py`
- 接口文档：`NestJS/API.md`
- 架构说明：`项目架构说明.md`
