"""eval 运行环境:挂载 ai-service,加载其 .env,初始化 DB 与模型来源。

eval 以 in-process 方式直接调用 ai-service 的 harness(不起 HTTP 服务),
因此运行前必须:
- 用 ai-service/.venv 的 python 运行(依赖零新增);
- ai-service/.env 已配置(模型网关密钥、DATABASE_URL)。

用户权限类写操作走 NestJS HTTP,e2e 套件涉及此类用例时需 NestJS(6011)在线。
"""
import os
import sys

EVAL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_SERVICE_DIR = os.path.normpath(os.path.join(EVAL_DIR, "..", "ai-service"))

_initialized = False


def setup() -> dict:
    """挂载 ai-service 并返回 PROVIDERS(与 app/main.py 同名同构)。"""
    global _initialized
    if _initialized:
        return providers()
    if AI_SERVICE_DIR not in sys.path:
        sys.path.insert(0, AI_SERVICE_DIR)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(AI_SERVICE_DIR, ".env"))
    from app.db import init_db
    init_db(os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./ai_service.db"))
    # 业务装配(规则/卡片钩子注册)在 import app.agent 时完成
    import app.agent  # noqa: F401
    _initialized = True
    return providers()


def providers() -> dict:
    """与 ai-service app/main.py 的 PROVIDERS 保持一致(只保留配了地址的)"""
    def _strip(url):
        return (url or "").rstrip("/")

    all_providers = {
        "company": {
            "key": "company",
            "name": "公司模型",
            "base_url": _strip(os.getenv("MODEL_BASE_URL")),
            "api_key": os.getenv("MODEL_API_KEY", ""),
        },
        "bailian": {
            "key": "bailian",
            "name": "百炼模型",
            "base_url": _strip(os.getenv("BAILIAN_MODEL_BASE_URL")),
            "api_key": os.getenv("BAILIAN_MODEL_API_KEY", ""),
        },
    }
    return {k: v for k, v in all_providers.items() if v["base_url"]}


def build_eval_agent(provider_key: str, model: str, user_id: str = "eval",
                     with_rag: bool = False, checkpointer=None,
                     body: dict | None = None):
    """构造评测用 Agent(复用业务装配,保证测的就是线上跑的东西)。"""
    from app.agent import build_agent
    provider = providers()[provider_key]
    embed_provider = None
    if with_rag:
        embed_provider = providers().get(os.getenv("EMBED_PROVIDER", "bailian"))
    return build_agent(
        provider, model, body or {},
        user_id=user_id,
        embed_provider=embed_provider,
        embed_model=os.getenv("EMBED_MODEL", "text-embedding-v3"),
        checkpointer=checkpointer,
    )
