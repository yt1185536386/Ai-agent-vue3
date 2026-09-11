"""模型来源注册表:channels 表为唯一数据源(与 NestJS ModelsService 语义对齐)。

- registry.py  15s TTL 缓存 + 未命中强刷;渠道真实地址/密钥永不下发,调用统一走 Java 网关

从哪里入手学习:registry.py 单文件即可,重点看缓存策略注释(为什么空结果不能用环境变量绕过)。
"""
