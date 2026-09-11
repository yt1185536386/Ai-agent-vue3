"""基础设施层:数据库会话/ORM 基类 + FastAPI 鉴权依赖。

- db.py    异步引擎/会话工厂/init_db + 会话与消息两表(展示轨道存储)
- deps.py  服务间鉴权(require_service_key)与管理台鉴权(require_admin_user)

从哪里入手学习:先 db.py 看两轨模型的 MySQL 侧,再 deps.py 理解三类调用方
(NestJS / 管理台 vite 代理 / 内部)怎么鉴权。
"""
