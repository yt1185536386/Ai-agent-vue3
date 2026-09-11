"""/v1/pe/* 路由:Prompt 模板管理 + prompt 维度指标。

鉴权:require_admin_user(管理台经 vite 代理直连;细粒度权限码在
NestJS 侧校验,prompt:manage / prompt:view)。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import require_admin_user
from app.prompteng import metrics, service

router = APIRouter(
    prefix="/v1/pe", tags=["prompteng"],
    dependencies=[Depends(require_admin_user)],
)


@router.get("/templates")
async def list_templates(
    group: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """模板列表(可按 group 过滤)"""
    return {"templates": await service.list_templates(session, group)}


@router.post("/templates", status_code=201)
async def create_template(body: dict, session: AsyncSession = Depends(get_session)):
    """新建模板(自动建 v1 draft)"""
    try:
        return await service.create_template(
            session,
            key=(body.get("key") or "").strip(),
            name=(body.get("name") or "").strip() or (body.get("key") or "").strip(),
            group=body.get("group") or "other",
            description=body.get("description") or "",
            content=body.get("content") or "",
            variables=body.get("variables"),
            note=body.get("note") or "初始版本",
        )
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.get("/templates/{key}/versions")
async def list_versions(key: str, session: AsyncSession = Depends(get_session)):
    """版本列表(倒序)"""
    try:
        return {"versions": await service.list_versions(session, key)}
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.post("/templates/{key}/versions", status_code=201)
async def add_version(key: str, body: dict, session: AsyncSession = Depends(get_session)):
    """提交新版本(draft)"""
    try:
        return await service.add_version(
            session, key,
            content=body.get("content") or "",
            variables=body.get("variables"),
            note=body.get("note") or "",
        )
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.post("/templates/{key}/activate")
async def activate(key: str, body: dict, session: AsyncSession = Depends(get_session)):
    """激活指定版本(热更新 register_rules / 模板缓存,记录 note)"""
    try:
        return await service.activate(
            session, key, int(body.get("version")), note=body.get("note") or "")
    except KeyError as e:
        raise HTTPException(404, str(e))
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))


@router.post("/templates/{key}/disable")
async def disable(key: str, session: AsyncSession = Depends(get_session)):
    """停用,回退代码默认"""
    try:
        return await service.disable(session, key)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.delete("/templates/{key}")
async def delete_template(key: str, session: AsyncSession = Depends(get_session)):
    """删除模板整体(含所有版本)"""
    try:
        await service.delete_template(session, key)
        return {"ok": True}
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.put("/templates/{key}/versions/{version}")
async def update_version(
    key: str,
    version: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """编辑 draft 版本(内容/变量说明/备注),只能改 draft"""
    try:
        return await service.update_version(
            session, key, version,
            content=body.get("content"),
            variables=body.get("variables"),
            note=body.get("note"),
        )
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/templates/{key}/versions/{version}")
async def delete_version(
    key: str,
    version: int,
    session: AsyncSession = Depends(get_session),
):
    """删除指定版本,不能删当前激活版本"""
    try:
        await service.delete_version(session, key, version)
        return {"ok": True}
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/metrics/overview")
async def metrics_overview(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
):
    """看板聚合:各模板调用量、版本分布、token、通过率"""
    return await metrics.overview(session, days)


@router.get("/metrics/templates/{key}")
async def metrics_template(
    key: str,
    days: int = Query(default=14, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
):
    """单模板趋势(按天 × 按版本)"""
    return await metrics.template_trend(session, key, days)


@router.get("/assemblies")
async def recent_assemblies(limit: int = Query(default=50, ge=1, le=200)):
    """最近的 prompt 装配记录(内存观测,调试用)"""
    return {"assemblies": service.recent_assemblies(limit)}
