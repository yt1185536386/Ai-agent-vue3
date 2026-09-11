"""模板 CRUD、版本激活、渲染;维护「激活模板内存缓存」供 harness 钩子同步读取。

缓存是唯一被主链路读取的结构:
- harness/prompts.py 的 set_template_loader 注入 load_content(同步、无 IO);
- DB 变更(激活/停用)只在管理面发生,变更后刷新缓存并做副作用
  (rules.* 模板调 register_rules 热更新规则块)。

渲染约定:变量用 {{var}} 占位,简单文本替换(非 Jinja,避免模板注入)。
内置变量:agent.system 模板支持 {{time}}(当前时间)、{{rules}}(业务规则块)。
"""
import json
import logging
import re
import uuid
from collections import deque
from datetime import datetime

from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.prompteng.models import PeTemplate, PeTemplateVersion

log = logging.getLogger(__name__)

# 激活模板缓存:key -> {"content": 模板文本, "version": 版本号}
_CACHE: dict[str, dict] = {}

# 最近装配记录(观测用,内存环形缓冲,不落库)
_recent_assemblies: deque = deque(maxlen=200)

_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


# ---------- 缓存读取(harness 钩子注入点,同步、无 IO) ----------

def load_content(key: str) -> str | None:
    """模板加载注入点:返回激活模板文本;无 DB 模板/已停用返回 None(代码默认)"""
    item = _CACHE.get(key)
    return item["content"] if item else None


def active_version(key: str) -> int:
    """当前激活版本号;无 DB 模板返回 0(表示代码内默认)"""
    item = _CACHE.get(key)
    return item["version"] if item else 0


def record_assembly(event: dict) -> None:
    """装配完成钩子:记录最近一次装配(轻量内存观测,不落库)。
    harness 传的 version 恒 0,这里按缓存补全实际激活版本"""
    try:
        event = dict(event)
        if not event.get("version"):
            event["version"] = active_version(event.get("template_key", ""))
        _recent_assemblies.append({**event, "at": datetime.utcnow().isoformat()})
    except Exception:
        pass


def recent_assemblies(limit: int = 50) -> list[dict]:
    return list(_recent_assemblies)[-limit:]


def render(content: str, variables: dict[str, str]) -> str:
    """简单变量替换:{{var}} → variables[var];未提供的变量保留原样"""
    def _sub(m):
        return variables.get(m.group(1), m.group(0))
    return _VAR_RE.sub(_sub, content)


# ---------- 缓存刷新 ----------

async def refresh_cache() -> None:
    """启动/变更后调用:从 DB 重建激活缓存,并应用副作用(rules 热更新)"""
    from app.core.db import sessionmaker
    from app.agent.prompts import register_rules
    async with sessionmaker()() as s:
        rows = (await s.execute(
            select(PeTemplate, PeTemplateVersion)
            .join(PeTemplateVersion,
                  (PeTemplateVersion.template_id == PeTemplate.id)
                  & (PeTemplateVersion.status == "active"))
            .where(PeTemplate.status == "active")
        )).all()
    new_cache: dict[str, dict] = {}
    for tpl, ver in rows:
        new_cache[tpl.key] = {"content": ver.content, "version": ver.version}
    _CACHE.clear()
    _CACHE.update(new_cache)
    # 副作用:rules.* 模板 → 热更新 harness 规则注册表
    for key, item in new_cache.items():
        if key.startswith("rules."):
            try:
                register_rules(key[len("rules."):], item["content"])
            except Exception:
                log.warning("rules 热更新失败 key=%s", key)


# ---------- 序列化 ----------

def serialize_template(t: PeTemplate) -> dict:
    return {
        "id": t.id, "key": t.key, "name": t.name, "group": t.group,
        "description": t.description, "status": t.status,
        "current_version": t.current_version,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def serialize_version(v: PeTemplateVersion) -> dict:
    return {
        "id": v.id, "template_id": v.template_id, "version": v.version,
        "content": v.content,
        "variables": json.loads(v.variables or "[]"),
        "status": v.status, "note": v.note,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


# ---------- CRUD ----------

async def list_templates(session: AsyncSession, group: str | None = None) -> list[dict]:
    stmt = select(PeTemplate).order_by(PeTemplate.group, PeTemplate.key)
    if group:
        stmt = stmt.where(PeTemplate.group == group)
    rows = (await session.execute(stmt)).scalars().all()
    return [serialize_template(t) for t in rows]


async def create_template(
    session: AsyncSession, *, key: str, name: str, group: str = "other",
    description: str = "", content: str = "", variables: list | None = None,
    note: str = "初始版本",
) -> dict:
    """新建模板(自动建 v1 draft);key 已存在抛 ValueError"""
    exists = (await session.execute(
        select(PeTemplate).where(PeTemplate.key == key))).scalar_one_or_none()
    if exists:
        raise ValueError(f"模板 key 已存在: {key}")
    tpl = PeTemplate(
        id=uuid.uuid4().hex, key=key, name=name, group=group,
        description=description, status="active", current_version=0)
    ver = PeTemplateVersion(
        id=uuid.uuid4().hex, template_id=tpl.id, version=1, content=content,
        variables=json.dumps(variables or [], ensure_ascii=False),
        status="draft", note=note)
    session.add_all([tpl, ver])
    await session.commit()
    return serialize_template(tpl)


async def list_versions(session: AsyncSession, key: str) -> list[dict]:
    tpl = await _get_by_key(session, key)
    rows = (await session.execute(
        select(PeTemplateVersion)
        .where(PeTemplateVersion.template_id == tpl.id)
        .order_by(PeTemplateVersion.version.desc())
    )).scalars().all()
    return [serialize_version(v) for v in rows]


async def add_version(
    session: AsyncSession, key: str, *, content: str,
    variables: list | None = None, note: str = "",
) -> dict:
    """提交新版本(draft,不影响线上);模板不存在抛 KeyError"""
    tpl = await _get_by_key(session, key)
    next_ver = tpl.current_version
    rows = (await session.execute(
        select(PeTemplateVersion.version)
        .where(PeTemplateVersion.template_id == tpl.id)
        .order_by(PeTemplateVersion.version.desc()).limit(1)
    )).scalars().all()
    next_ver = (rows[0] if rows else 0) + 1
    ver = PeTemplateVersion(
        id=uuid.uuid4().hex, template_id=tpl.id, version=next_ver,
        content=content, variables=json.dumps(variables or [], ensure_ascii=False),
        status="draft", note=note)
    session.add(ver)
    tpl.updated_at = datetime.utcnow()
    await session.commit()
    return serialize_version(ver)


async def activate(session: AsyncSession, key: str, version: int, note: str = "") -> dict:
    """激活指定版本:同模板其他版本归 archived,刷新缓存(热更新生效)"""
    tpl = await _get_by_key(session, key)
    target = (await session.execute(
        select(PeTemplateVersion).where(
            PeTemplateVersion.template_id == tpl.id,
            PeTemplateVersion.version == version)
    )).scalar_one_or_none()
    if not target:
        raise ValueError(f"版本不存在: {key} v{version}")
    await session.execute(
        sql_update(PeTemplateVersion)
        .where(PeTemplateVersion.template_id == tpl.id,
               PeTemplateVersion.status == "active")
        .values(status="archived"))
    target.status = "active"
    if note:
        target.note = note
    tpl.current_version = version
    tpl.status = "active"
    tpl.updated_at = datetime.utcnow()
    await session.commit()
    await refresh_cache()
    return serialize_template(tpl)


async def disable(session: AsyncSession, key: str) -> dict:
    """停用模板:回退代码内默认(缓存移除,版本记录保留)"""
    tpl = await _get_by_key(session, key)
    tpl.status = "disabled"
    tpl.updated_at = datetime.utcnow()
    await session.commit()
    await refresh_cache()
    return serialize_template(tpl)


async def update_version(
    session: AsyncSession, key: str, version: int, *,
    content: str | None = None,
    variables: list | None = None,
    note: str | None = None,
) -> dict:
    """编辑 draft 版本:只能修改 status=draft 的版本,线上 active/archived 不能改"""
    tpl = await _get_by_key(session, key)
    ver = (await session.execute(
        select(PeTemplateVersion).where(
            PeTemplateVersion.template_id == tpl.id,
            PeTemplateVersion.version == version)
    )).scalar_one_or_none()
    if not ver:
        raise KeyError(f"版本不存在: {key} v{version}")
    if ver.status != "draft":
        raise ValueError(f"只能编辑 draft 版本,当前状态: {ver.status}")
    if content is not None:
        ver.content = content
    if variables is not None:
        ver.variables = json.dumps(variables, ensure_ascii=False)
    if note is not None:
        ver.note = note
    ver.created_at = datetime.utcnow()
    tpl.updated_at = datetime.utcnow()
    await session.commit()
    return serialize_version(ver)


async def delete_version(session: AsyncSession, key: str, version: int) -> None:
    """删除指定版本;不能删除当前 active 版本,避免线上模板悬空"""
    tpl = await _get_by_key(session, key)
    ver = (await session.execute(
        select(PeTemplateVersion).where(
            PeTemplateVersion.template_id == tpl.id,
            PeTemplateVersion.version == version)
    )).scalar_one_or_none()
    if not ver:
        raise KeyError(f"版本不存在: {key} v{version}")
    if ver.status == "active":
        raise ValueError(f"不能删除当前激活版本: {key} v{version}")
    await session.delete(ver)
    # 若删除的是最高 draft,current_version 仍保留为最新 active(或 0)
    tpl.updated_at = datetime.utcnow()
    await session.commit()


async def delete_template(session: AsyncSession, key: str) -> None:
    """删除模板整体(含所有版本);级联删除由 ORM/FK 处理"""
    tpl = await _get_by_key(session, key)
    await session.delete(tpl)
    await session.commit()
    await refresh_cache()


async def _get_by_key(session: AsyncSession, key: str) -> PeTemplate:
    tpl = (await session.execute(
        select(PeTemplate).where(PeTemplate.key == key))).scalar_one_or_none()
    if not tpl:
        raise KeyError(f"模板不存在: {key}")
    return tpl
