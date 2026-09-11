# 模型服务网关 (model-gateway)

系统的**唯一模型出口**:所有模型调用(对话 / embedding)都经此网关,
限流 / 熔断 / 计量 / 渠道调度在这里透明完成。Java / Spring Boot 3 实现。

## 在系统中的位置(2026-08 重构)

```
浏览器 → NestJS 网关 (6011,唯一用户权限权威: JWT 签发/权限点/规则引擎)
           │  X-Service-Key + X-User-Id + X-Username
           ▼
        ai-service (6010,Agent 编排)
           │  Authorization: Bearer <service-key> + X-Channel-Key + X-User-Id
           ▼
        model-gateway (6015,本服务,唯一模型出口)
           ▼
        company / 百炼 真实上游(真实 baseUrl/apiKey 只配置在 channels 表)
```

职责切分:
- **NestJS**:用户/部门/职级/权限的唯一权威,JWT 只在这里签发,业务规则引擎只在这里实现。
  权限模型 = `isSuperAdmin` + 两维绑定:职级批量绑定 + 个人逐项覆盖(个人优先于职级)。
- **model-gateway**:不持有用户权限语义。`/v1/**` 只认内部服务密钥
  (与 NestJS↔ai-service 的 `NESTJS_SERVICE_KEY` 同值),用户身份经
  `X-User-Id` / `X-Username`(URL 编码)透传,仅作用户维度限流/计量。
- 管理端 UI(ServerManegeUI)登录走 NestJS;本网关只**校验** NestJS 签发的
  JWT(共享密钥),不签发。权限/禁用状态每次请求从共享 users 表重读并解析
  有效权限码,立即生效。

| 模块 | 包 | 说明 |
| --- | --- | --- |
| 鉴权 | `auth`/`perm` | `ServiceKeyInterceptor`(/v1,内部服务密钥)+ `AuthInterceptor`(/api,校验 NestJS JWT,解析 `isSuperAdmin` + 有效权限码)+ `@RequirePermission` |
| 用户查询 | `user` | 只读列表(写操作已收敛到 NestJS,避免绕过规则引擎直写共享表) |
| 部门/职级/权限 | — | 只读共享 NestJS 表,model-gateway 仅做权限码校验 |
| 仓库管理 | `repo` | 模型渠道接入点:baseUrl/apiKey/模型列表/channelKey/优先级/启停;`X-Channel-Key` 头按 key 精确路由,缺省按模型列表匹配 |
| 限流熔断 | `ratelimit` | 令牌桶限流(QPM/TPM,全局/用户/渠道维度)+ 滑动窗口失败率熔断 |
| 模型调用 | `invoke` | `/v1/chat/completions`(SSE 流式原生透传)/ `/v1/embeddings` / `/v1/models`,计量落库(`invoke_logs`,流式从流末 usage 块提取真实 token 用量) |
| 数据概览 | `stats` | 看板聚合:调用量/Token/QPM/TPM/错误率/用户×模型分布/趋势 |

## 运行

```bash
# 连接 MySQL(与 NestJS 共用 ai_agent 库),推荐方式:
powershell -File run-mysql.ps1
```

`run-mysql.ps1` 从 `../NestJS/.env` 读取 DB / JWT_SECRET / NESTJS_SERVICE_KEY,
渠道表为空时按脚本内 `CHANNEL_*` 变量播种 company / bailian 真实渠道。
端口 `6015`。

> 注意:`Get-Content` 必须带 `-Encoding UTF8`(PowerShell 5.1 默认按 GBK 读
> 无 BOM 的 UTF-8,中文注释行会吞掉换行导致后续 KEY 解析丢失)。

默认 H2 内存库模式(`mvn spring-boot:run`)保留用于本地试跑,
但管理端登录已收敛到 NestJS,独立演示能力有限。

## 主要接口

```
# /v1: 内部调用方(ai-service 等),X-Service-Key 或 Authorization: Bearer <service-key>
POST /v1/chat/completions              OpenAI 兼容入口(stream=true 时 SSE 原生透传)
POST /v1/embeddings                    embedding 透传(RAG 向量化)
GET  /v1/models                        模型列表(带 X-Channel-Key 透传该渠道上游,否则本地聚合)

# /api: 管理端(ServerManegeUI),NestJS 签发的 JWT
GET  /api/auth/me                      当前用户
GET  /api/users                        用户列表(只读)
GET|POST|PUT|DELETE /api/channels      渠道管理(仅超级管理员)
GET|POST|PUT|DELETE /api/policies      限流/熔断策略(需 `policy:manage`)
GET  /api/policies/{id}/circuit-state  熔断器实时状态(需 `policy:manage`)
POST /api/invoke/chat                  调试台调用(登录即可)
GET  /api/logs                         调用日志(需 `log:view`,唯一计量来源)
GET  /api/stats/overview               数据看板聚合(仅超级管理员)
GET  /api/stats/realtime               最近一分钟实时指标(仅超级管理员)
```

业务方接入:把 OpenAI SDK 的 `baseURL` 指向 `http://<gateway>:6015/v1`,
`apiKey` 用内部服务密钥;可选 `X-Channel-Key` 头指定渠道,否则按模型名匹配渠道。
