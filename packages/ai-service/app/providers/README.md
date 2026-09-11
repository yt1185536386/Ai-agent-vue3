# providers — 模型来源注册表

> 回答"这次对话用哪个模型、走哪个网关渠道"。单文件约 115 行。

## 文件地图

| 文件 | 职责 |
|---|---|
| `registry.py` | 以 Java 网关 channels 表为唯一数据源:15s TTL 缓存 + 未命中强刷 + 失败保留旧缓存 + 环境变量兜底 |

## 必读的安全约定(模块 docstring 原文)

- base_url/api_key **不下发渠道里的上游真实地址与密钥**
- 调用统一经 Java model-gateway(MODEL_BASE_URL + 内部服务密钥),渠道 key 经 `X-Channel-Key` 头传给网关做路由
- **channels 表查询成功但为空时原样返回空**——管理端全部停用时不能拿环境变量绕过禁用(这是刻意的安全语义,别"修"掉)

## 学习路径

单文件自顶向下:缓存策略 → `get_provider`(查 channels 表)→ `_env_providers`(兜底来源)。
消费方:`main.py`(chat 入口选 provider)、`agent/client.py`(组装调用头)、`rag/engine.py`(embedding)。

## 优化切入点

- 缓存是进程内存:多实例部署时各实例 15s 不一致 → 可接 Redis pub/sub 主动失效
- `EMBED_PROVIDER` 环境变量选 embedding 来源,与对话来源解耦但同走网关,可考虑入 channels 表统一管理
