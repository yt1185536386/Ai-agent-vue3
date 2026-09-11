# core — 基础设施层

> 全服务共用的地基:数据库与鉴权。约 260 行。

## 文件地图

| 文件 | 职责 |
|---|---|
| `db.py` | 异步引擎/`sessionmaker`/`init_db` + Conversation/Message 两表(展示轨道存储)+ 消息增删查工具函数 |
| `deps.py` | FastAPI 鉴权依赖:`require_service_key`(NestJS → ai-service,密钥+X-User-Id)、`require_admin_user`(管理台 vite 代理直连) |

## 学习路径

1. `db.py` 先看两表模型(Conversation/Message),注意 **messages 表是展示轨道唯一权威**(推理轨道在 agent 的 checkpoints.db,两轨设计见 persistence/README)
2. `deps.py` 理解三类调用方:内部服务(NestJS,持密钥)/ 管理台(不持密钥,要求 X-User-Id)/ 公开(/health)

## 优化切入点

- `deps.py`:管理台鉴权偏弱(仅要求 X-User-Id 非空),细粒度权限码(prompt:manage / ctx:view)应在此落地校验
- `deps.py`:密钥比较可改常量时间比较(与 NestJS/Java 侧对齐)
- `db.py`:连接池参数未显式配置,并发上来后需要调
