"""
模型来源注册表:以 model-gateway 的 channels 表为唯一数据源(与 NestJS
ModelsService 语义对齐:status=1 且 channelKey 非空,按 priority 排序)。

安全约定与 NestJS 一致:base_url/api_key 不下发渠道里的上游真实地址与密钥,
调用统一经 Java model-gateway(MODEL_BASE_URL + 内部服务密钥),key 经
X-Channel-Key 头传给网关做渠道路由,限流/熔断/计量都在网关侧完成。

缓存策略:15s TTL + 未命中强制刷新(管理端新增渠道后首次调用即可见)。
查库失败时保留旧缓存;进程内还没有任何缓存时回落到环境变量构造的静态来源,
保证首次部署/网关未建表时可用。channels 表查询成功但为空时原样返回空
(管理端全部停用时客户端不应看到任何来源,不能用环境变量绕过禁用)。
"""
import logging
import os
import time

from sqlalchemy import text

log = logging.getLogger(__name__)

CACHE_TTL = 15.0
_cache_at = 0.0


def _strip(url: str | None) -> str:
    return (url or "").rstrip("/")


def _bit(v) -> bool:
    """MySQL BIT(1) 经 aiomysql 读出为 bytes(b'\\x00'/b'\\x01'),统一转 bool"""
    return v is True or v == 1 or v == b"\x01"


def _env_providers() -> dict[str, dict]:
    """环境变量构造的兜底来源(仅在查库失败且无任何缓存时使用)"""
    providers = {
        "company": {
            "key": "company",
            "name": "公司模型",
            "base_url": _strip(os.getenv("MODEL_BASE_URL")),
            "api_key": os.getenv("MODEL_API_KEY", ""),
            "enable_search": os.getenv("MODEL_ENABLE_SEARCH") == "true",
            "supports_tools": os.getenv("MODEL_ENABLE_TOOLS", "false") == "true",
        },
        "bailian": {
            "key": "bailian",
            "name": "百炼模型",
            "base_url": _strip(os.getenv("BAILIAN_MODEL_BASE_URL")),
            "api_key": os.getenv("BAILIAN_MODEL_API_KEY", ""),
            "enable_search": os.getenv("BAILIAN_MODEL_ENABLE_SEARCH") == "true",
            "supports_tools": os.getenv("BAILIAN_MODEL_ENABLE_TOOLS", "true") == "true",
        },
    }
    # 只保留配置了地址的来源
    return {k: v for k, v in providers.items() if v["base_url"]}


# 进程内来源缓存:原地更新(clear+update)而非重绑,main.py 等处以
# `from app.providers.registry import PROVIDERS` 持有的引用始终读到最新数据
PROVIDERS: dict[str, dict] = _env_providers()


async def refresh_providers(force: bool = False) -> None:
    """从 channels 表刷新来源缓存;失败时保留旧缓存"""
    global _cache_at
    if not force and time.monotonic() - _cache_at < CACHE_TTL:
        return
    _cache_at = time.monotonic()

    # 延迟 import:db 引擎在 lifespan 里 init_db 之后才可用
    from app.core.db import sessionmaker

    try:
        async with sessionmaker()() as session:
            rows = (await session.execute(text(
                "SELECT channelKey, name, enableSearch, supportsTools "
                "FROM channels WHERE status = 1 "
                "AND channelKey IS NOT NULL AND channelKey != '' "
                "ORDER BY priority ASC, name ASC"
            ))).all()
    except Exception as e:
        log.warning("读取 channels 表失败,保留现有来源缓存: %s", e)
        if not PROVIDERS:
            PROVIDERS.update(_env_providers())
        return

    # 调用入口统一为 Java model-gateway;上游真实地址/密钥留在网关侧
    gateway_base = _strip(os.getenv("MODEL_BASE_URL"))
    service_key = os.getenv("MODEL_API_KEY", "")
    new: dict[str, dict] = {}
    for key, name, enable_search, supports_tools in rows:
        new[key] = {
            "key": key,
            "name": name,
            "base_url": gateway_base,
            "api_key": service_key,
            "enable_search": _bit(enable_search),
            "supports_tools": _bit(supports_tools),
        }
    if not new and not PROVIDERS:
        # 首次启动表为空:回落环境变量,保证首次部署可用
        new = _env_providers()
    PROVIDERS.clear()
    PROVIDERS.update(new)
    log.info("模型来源已刷新: %s", list(PROVIDERS))


async def get_provider(key: str) -> dict | None:
    """按 key 取来源;TTL 过期或缓存未命中时先刷新(新增渠道立即生效)"""
    p = PROVIDERS.get(key)
    if p is None or time.monotonic() - _cache_at > CACHE_TTL:
        await refresh_providers(force=p is None)
        p = PROVIDERS.get(key)
    return p
