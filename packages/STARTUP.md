# 启动指南(STARTUP)

`packages/` 下的常驻服务:ai-service / NestJS / Java model-gateway / 两个前端,
外加按需运行的 eval 评测包。端口集中在各项目的 `.env` 文件中。

> 模块职责见 [项目架构说明.md](项目架构说明.md);
> 一条消息的完整生命周期见 [Chatflow.md](Chatflow.md);
> 评测包详细用法见 [eval/README.md](eval/README.md)。

## 项目与端口

| 项目 | 目录 | 端口 | 启动命令 | 端口配置 |
|---|---|---|---|---|
| AI 服务(Agent 编排) | `ai-service/` | 26010 | uvicorn(见下) | `ai-service/.env` 的 `PORT` |
| NestJS 网关(鉴权 + 业务) | `NestJS/` | 26011 | `npm run start:dev` | `NestJS/.env` 的 `PORT` |
| Vue 前端 | `my-vue-app-ts/` | 26012 | `npm run dev` | `my-vue-app-ts/.env` 的 `VITE_PORT` |
| 管理端 UI | `ServerManegeUI/` | 26013 | `npm run dev` | `ServerManegeUI/vite.config.ts` |
| Java 模型网关(唯一模型出口) | `model-gateway/` | 26015 | `powershell -File run-mysql.ps1` | `model-gateway` application.yml 的 `PORT` |
| RAG 服务 | `rag-service/` | 26016 | `powershell -File start-rag.ps1` | `rag-service` application.yml 的 `PORT` |
| eval 评测包 | `eval/` | —(不占端口) | `run_eval.py`(见下) | 复用 `ai-service/.env` |

> 端口段统一规划为 **26010-26016**(2026-09 从 6010-6016 迁入,2601x 段极少被
> 其他软件占用,且避开 Windows Hyper-V/WSL 保留段 50000-50059)。
> 26014 空出来不用:my-vue-app-ts 的 vite 在 26012 被占时会自增到 26013/26014。

## 一键启动/重启(推荐)

```powershell
powershell -ExecutionPolicy Bypass -File packages/start-all-detached.ps1
```

该脚本会**先清理再启动**,两步清理缺一不可:

1. **按端口清理**:杀掉 26010-26013/26015/26016 上的监听进程树;
2. **按进程特征清理**:杀掉本项目残留的 `node`(nest --watch / vite)、
   `python`(uvicorn --reload 父进程)、`java`(spring-boot:run)。

> 为什么必须清第 2 步:只杀监听端口的子进程时,`nest --watch` /
> `uvicorn --reload` 的父进程仍存活,会自动重新拉起实例,与手工启动的
> 新实例互抢端口,造成 EADDRINUSE 死循环(NestJS 曾因此反复崩溃)。

## 调用链

```
浏览器 (http://localhost:26012)
  → Vite 代理 /api
    → NestJS 网关 (26011,JWT 鉴权 + 业务接口,唯一用户权限权威)
      → ai-service (26010,harness:ReAct 循环 + SSE)
        → Java model-gateway (26015,唯一模型出口:限流/熔断/计量/渠道调度)
          → 上游模型提供方 (company / 百炼,真实 key 只配置在 channels 表)
```

管理端 (http://localhost:26013):登录走 NestJS(共享 JWT),
渠道/策略/日志/看板直连 model-gateway /api。

eval 不在链路上:它以 in-process 方式直接调用 ai-service 的 harness,
用真实模型跑评测用例,不影响三个服务。

## 前置条件

- Node.js 20+ 与 npm
- Python 3.11+,`ai-service/.venv` 已创建(eval 复用同一 venv,零新增依赖);
  重建环境用 `pip install -r requirements.txt`(langgraph 1.2.9 等版本已锁定,
  子图事件命名空间行为依赖该版本实测)
- MySQL 运行于 `localhost:3306`,数据库 `ai_agent`
  (业务数据 + 会话/RAG 持久化都在里面;`DATABASE_URL` 未配置时 ai-service 退回本地 SQLite)
- 模型上游可达:公司 `http://172.18.200.114:3000/v1` 或百炼 dashscope
  (真实 baseUrl/apiKey 只配置在 model-gateway 的 channels 表,
  由各服务 `.env` 指向 26015;`run-mysql.ps1` 首次启动会播种渠道)

## 启动

### 1. AI 服务(ai-service)

```bash
cd ai-service
.venv/Scripts/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 26010
```

> 用 `127.0.0.1` 而不是 `0.0.0.0`:本机 WPS 云服务(wpscloudsvr.exe)
> 曾占用 8888 的出站连接导致 `0.0.0.0` 绑定报 WinError 10048/10013。
> 本地开发只走 loopback,效果相同且更稳。

`--reload` 会监视 `app/` 下的改动自动重启(harness/tools/业务模块都算)。

健康检查:`curl http://localhost:26010/health`
(返回 `{"status":"ok","providers":[...]}`)

### 2. NestJS 网关

```bash
cd NestJS
npm run start:dev
```

读取 `NestJS/.env` 的 `PORT=26011`;启动日志出现
`Nest application successfully started` 即就绪。

### 3. Vue 前端

```bash
cd my-vue-app-ts
npm run dev
```

Vite 读取 `my-vue-app-ts/.env` 的 `VITE_PORT=26012`,
代理目标取 `NESTJS_PORT=26011`。

### 4. eval 评测包(按需,不常驻)

```bash
cd eval
../ai-service/.venv/Scripts/python run_eval.py --suite all
# 单套件:--suite tool_selection / e2e / quality / regression
# 换模型:--provider bailian --model qwen-plus --judge qwen-max
```

报告写入 `eval/reports/`;全部通过退出码 0,可直接接 CI。

## 环境变量速查

| 变量 | 位置 | 用途 |
|---|---|---|
| `PORT` | `ai-service/.env` | ai-service 监听端口 |
| `DATABASE_URL` | `ai-service/.env` | 会话/消息/文档/向量持久化(当前指向 MySQL `ai_agent`) |
| `EMBED_PROVIDER` / `EMBED_MODEL` | `ai-service/.env` | RAG embedding 来源与模型 |
| `ASR_MODEL` | `ai-service/.env` | 语音识别模型(默认 `paraformer-realtime-v2`,复用百炼 key) |
| `MODEL_ENABLE_TOOLS` / `BAILIAN_MODEL_ENABLE_TOOLS` | `ai-service/.env` | 来源是否支持 tool_calls(Agent 路径开关) |
| `THINKING_MODELS` | `ai-service/.env` | 支持思考模式的模型(名称匹配) |
| `PORT` | `NestJS/.env` | NestJS 监听端口 |
| `AI_SERVICE_URL` | `NestJS/.env` | NestJS → ai-service 转发地址 |
| `NESTJS_SERVICE_KEY` | 两个 `.env` 各一份 | 内部服务密钥,两边必须一致 |
| `VITE_PORT` / `NESTJS_PORT` | `my-vue-app-ts/.env` | 前端端口 / 代理目标端口 |

源码 fallback 与 `.env` 默认值保持同步,缺 `.env` 也能按规范端口启动:

- `NestJS/src/main.ts`:`process.env.PORT ?? 26011`
- `NestJS/src/chat/chat.service.ts`:`AI_SERVICE_URL ?? 'http://localhost:26010'`
- `my-vue-app-ts/vite.config.ts`:`VITE_PORT ?? '26012'`、`NESTJS_PORT ?? '26011'`

## 修改端口

改对应 `.env` 后重启服务。若改 NestJS 端口,必须同步改
`my-vue-app-ts/.env` 的 `NESTJS_PORT`,否则前端代理失效;
若改 ai-service 端口,同步改 `NestJS/.env` 的 `AI_SERVICE_URL`。

## 验证

```bash
curl http://localhost:26010/health   # AI 服务
curl http://localhost:26011          # NestJS(返回根响应)
# 前端:浏览器打开 http://localhost:26012
```

端到端:在 Vue 应用里发一条对话,链路应为 `26012 → 26011 → 26010`;
再问一句需要工具的问题(如「长沙天气怎么样」)观察工具步骤与卡片渲染。

## Windows 后台运行提示

终端里 `&` 启动的进程会随会话结束被杀。需要 detached 运行时,用
PowerShell `Start-Process` 并把输出重定向到各项目下的 `dev-out.log` /
`dev-err.log`;重启前先 `netstat -ano | findstr :26010` 检查端口是否被旧进程占用。
