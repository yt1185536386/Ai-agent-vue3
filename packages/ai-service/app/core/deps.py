"""共享 FastAPI 依赖:内部鉴权。

require_service_key: NestJS 网关 → ai-service 的服务间鉴权(原有约定)。
require_admin_user:   管理台(ServerManegeUI)→ /v1/pe /v1/cx 的鉴权。
  管理台经 vite 代理直连 ai-service,不持有服务密钥;此处要求 X-User-Id 非空,
  若携带 X-Service-Key 则必须匹配。细粒度权限码(prompt:manage 等)在
  NestJS 侧与前端菜单层校验(见改造计划 §7.3)。
"""
import os

from fastapi import Header, HTTPException


def _service_key() -> str | None:
    # 延迟读取:main.py 在 import 后才 load_dotenv
    return os.getenv("NESTJS_SERVICE_KEY")


async def require_service_key(
    x_service_key: str = Header(default=""),
    x_user_id: str | None = Header(default=None),
) -> str:
    """校验 NestJS 传来的内部服务密钥,并确保 user_id 非空"""
    key = _service_key()
    if not key:
        raise HTTPException(500, "AI 服务未配置 NESTJS_SERVICE_KEY")
    if x_service_key != key:
        raise HTTPException(401, "Invalid service key")
    if not x_user_id:
        raise HTTPException(400, "Missing X-User-Id")
    return x_user_id


async def require_admin_user(
    x_service_key: str = Header(default=""),
    x_user_id: str | None = Header(default=None),
) -> str:
    """管理台端点鉴权:X-User-Id 必填;携带服务密钥时必须匹配"""
    if not x_user_id:
        raise HTTPException(400, "Missing X-User-Id")
    key = _service_key()
    if x_service_key and key and x_service_key != key:
        raise HTTPException(401, "Invalid service key")
    return x_user_id
