# V3Agent

多包单体仓库:AI 对话助手全栈,含业务前端、管理端、三个后端服务与一个 Java 模型网关。

```
packages/
├── my-vue-app-ts/    业务对话端(Vue3+Vite, :6012)
├── ServerManegeUI/   管理端(Vue3+Element Plus, :6013)
├── NestJS/           BFF 网关:鉴权/会话/规则引擎(:6011)
├── ai-service/       Agent 服务(FastAPI+LangGraph, :6010)
├── model-gateway/    Java 模型网关(Spring Boot, :6015)
├── rag-service/      向量检索服务(Spring Boot+pgvector)
└── eval/             Agent 离线评测脚本(Python)
```

## 环境要求

| 工具 | 版本 | 用于 |
|---|---|---|
| Node.js | ≥ 20 | 两个前端 + NestJS |
| Python | ≥ 3.11 | ai-service、eval |
| JDK | 21 | model-gateway、rag-service |
| Maven | 3.9+ | Java 构建 |
| MySQL | 8.x | NestJS(仅需要一个空库) |
| Docker | 可选 | rag-service 的 pgvector |

## 快速开始

### 0. 环境变量

每个包从模板复制并填入真实值(密钥不进仓库):

```bash
cp packages/NestJS/.env.example packages/NestJS/.env
cp packages/ai-service/.env.example packages/ai-service/.env
cp packages/my-vue-app-ts/.env.example packages/my-vue-app-ts/.env
```

关键约定:
- `NESTJS_SERVICE_KEY`(NestJS 与 ai-service)与 `GATEWAY_SERVICE_KEY`(model-gateway)
  必须**同值**——这是 NestJS/ai-service → Java 网关的内部调用凭据,Java 侧未配置会直接拒绝服务
- model-gateway 的 JWT 密钥(`gateway.jwt.secret`,见其 application.yml)与 NestJS 的
  `JWT_SECRET` 必须**同值**——JWT 由 NestJS 签发、Java 只校验
- ai-service 未配置模型渠道时会用 `.env` 里的 `MODEL_*` 兜底,配好渠道后以
  管理端维护的 channels 表为准

### 1. 数据库

NestJS 使用 MySQL,建一个空库即可(表结构由 `DB_SYNCHRONIZE=true` 自动创建,
**生产环境必须改 false 并走 migration**):

```sql
CREATE DATABASE ai_agent DEFAULT CHARACTER SET utf8mb4;
```

首次启动 NestJS 会自动播种超级管理员:`eric` / 密码取 `SEED_ADMIN_PASSWORD`
环境变量(未配置时为开发默认值 `eric123`,**部署环境务必显式配置**)。

### 2. 启动各服务(建议顺序)

```bash
# ⓪ RAG 向量检索(可选,需要 Docker)
cd packages/rag-service
docker compose up -d            # pgvector + init.sql;不启动则文档检索相关功能不可用

# ① Java 模型网关 —— 必须用 mysql profile + 三把密钥,否则管理端 401、内部调用被拒
#    推荐:根目录一键脚本(自动读 NestJS/.env 的 DB_*/JWT_SECRET/服务密钥)
powershell -ExecutionPolicy Bypass -File run-mysql.ps1
#    或手动(变量缺一不可: GATEWAY_SERVICE_KEY 与 NESTJS_SERVICE_KEY 同值;JWT_SECRET 同值;profile=mysql 共享用户库)
cd packages/model-gateway
GATEWAY_SERVICE_KEY=<同 NESTJS_SERVICE_KEY> JWT_SECRET=<同 NestJS> \
DB_USERNAME=... DB_PASSWORD=... \
mvn spring-boot:run -Dspring-boot.run.profiles=mysql
#    ⚠️ 裸 `java -jar`(默认 H2 内存库 + 无密钥)会导致:登录后接口全 401(网关查不到用户)、
#       ai-service 调网关被默认拒绝(模型列表失败)

# ② ai-service
cd packages/ai-service
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
.venv/Scripts/uvicorn app.main:app --port 6010

# ③ NestJS BFF
cd packages/NestJS
npm install && npm run start:dev

# ④ 业务前端
cd packages/my-vue-app-ts
npm install && npm run dev        # http://localhost:6012

# ⑤ 管理端(可选)
cd packages/ServerManegeUI
npm install && npm run dev        # http://localhost:6013
```

启动后自查(端口通即服务就绪):

| 服务 | 端口 | 健康检查 |
|---|---|---|
| model-gateway | 6015 | `curl http://localhost:6015/health` |
| ai-service | 6010 | `curl http://localhost:6010/docs`(Swagger) |
| NestJS BFF | 6011 | `curl http://localhost:6011` |
| 业务前端 | 6012 | 浏览器打开 |
| 管理端 | 6013 | 浏览器打开 |
| rag-service | 5432 | `docker compose ps` |

运行日志会自动写入 MySQL 各服务独立表(`log_nestjs` / `log_ai_service` /
`log_model_gateway`,见下文「运行日志落库」),排错时直接查表。

### 3. 首次配置

1. 管理端登录(超管账号见上),在「模型渠道」里创建渠道
   (名称/真实地址/密钥——密钥只存服务端,永不下发前端)
2. 业务前端登录后即可对话;上传文档走「文档管理」,Agent 会通过
   `search_docs` 工具自主检索

## 运行日志落库(MySQL)

三个后端服务的运行日志在控制台照常输出的同时,批量写入 MySQL(`ai_agent` 库)各自的表,
结构同构:`level / context / message / meta / created_at`。

| 服务 | 表 | 写入方实现 |
|---|---|---|
| NestJS BFF | `log_nestjs` | `DbLoggerService`(全局 logger,2s 攒批) |
| ai-service | `log_ai_service` | `app/dblog.py`(pymysql + 守护线程,复用 `DATABASE_URL`) |
| model-gateway | `log_model_gateway` | `MysqlLogAppender`(自定义 Logback Appender) |

- 表均自动创建;生产环境(`DB_SYNCHRONIZE=false`)预建用 `packages/NestJS/sql/log_tables.sql`
- 失败一律静默降级(只写 stderr):MySQL 不可用时行为与未改造前完全一致,绝不影响业务
- Java 网关连接信息优先读 `LOG_DB_URL / LOG_DB_USERNAME / LOG_DB_PASSWORD`,未配置时
  回退解析同仓库 `NestJS/.env` 的 `DB_*`
- 常用查询:按时间段排错 `SELECT * FROM log_ai_service WHERE created_at > NOW() - INTERVAL 1 HOUR AND level IN ('error','warn') ORDER BY created_at DESC;`

## 架构文档

- [双网关架构设计文档.md](./双网关架构设计文档.md) — NestJS/Java 网关职责、鉴权链路、安全基线
- [前端架构设计文档.md](./前端架构设计文档.md) — 两个前端的构建与分包设计
- [ai-service架构拆解报告.md](./ai-service架构拆解报告.md) — Agent 运行时/工具系统/Prompt 与 Context 工程
- 各包内另有细化文档:`packages/ai-service/app/README.md`(模块学习地图)、`packages/rag-service/README.md`

## 已知约定与注意事项

- **Vite 代理顺序**:`/v1/pe`、`/v1/cx` 必须写在 `/v1` 通配之前(见 my-vue-app-ts/vite.config.ts)
- **Element Plus 按需引入**:显式 `import { ElMessage }` 的调用需手动补样式导入(见 ServerManegeUI/src/main.ts)
- **echarts 按需注册**:统一走 `ServerManegeUI/src/utils/echarts.ts`,禁止直接 `import * as echarts`
- **X-Request-Id 全链路**:NestJS 生成 → ai-service 透传 → Java 落 `invoke_logs.requestId`,排障一个 ID 串三层
- **checkpoints.db / uploads/ 不进仓库**:会话状态与用户文档属运行时数据,克隆后自动重建/为空属正常现象
