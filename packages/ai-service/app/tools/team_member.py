"""团队成员写成工具(站在人环中 HITL 审批闭环里的写操作)。

与外部知识库检索工具(external_kb.py)同属"按上下文装配的业务工具"范式:
闭包注入发起请求的用户身份(user_id)与服务配置,AI 服务只做编排、不落地业务副作用。

本工具的关键点:
- 写操作(调整成员职级/转岗/部门内职位)是敏感动作,必须人工审批后才执行。
- 工具内部调用 langgraph.types.interrupt(value) 把图挂起,value 携带待审批明细;
  前端据此渲染审批卡(只读 value.action / value.detail)。
- 用户批准后,图从断点恢复,interrupt() 返回 Command(resume=...) 送达的决策字符串
  ("approve"/"reject"),只有 approve 才真正调 NestJS users 接口落库,并带
  X-HITL: approved 头把审计 outcome 记为 approved。
- 权限随职级自动继承,本工具不改个人权限覆盖/职级权限矩阵(留作后续)。
"""
import os

import httpx
from langchain_core.tools import tool
from langgraph.types import interrupt


def _nestjs_env():
    """读取 NestJS 业务服务地址与内部密钥(两者齐备才挂载工具)。"""
    base = os.getenv("NESTJS_SERVICE_BASE_URL", "http://localhost:26011").rstrip("/")
    key = os.getenv("NESTJS_SERVICE_KEY", "")
    return base, key


def build_query_team_members_tool(user_id: str):
    """构造"查询团队成员"只读工具,以发起请求的用户身份查询当前可见成员。

    user_id: 请求该 Agent 会话的 NestJS 用户 id(UUID);NestJS 服务层据此按
    listVisible 规则返回可见成员(超管全量 / 部门经理本部门子树 / 其余仅自己)。
    """
    base, key = _nestjs_env()

    @tool
    def query_team_members(keyword: str = "") -> str:
        """查询当前用户的团队成员(按权限返回可见成员)。

        keyword 可选,非空时按用户名/显示名/部门/职级做模糊过滤;为空返回全部可见成员。
        当用户问"我的团队/团队成员都有谁、某部门的成员、某成员资料"时调用。
        注意:这是只读查询;执行职级调整/转岗等写操作请用 adjust_team_member。"""
        return _fetch_users(base, key, user_id, keyword)

    return query_team_members


def _fetch_users(base: str, key: str, user_id: str, keyword: str = "") -> str:
    """调 NestJS GET /v1/users 拉取可见成员,拼成模型易读的多行文本。"""
    import json

    if not key:
        return ("成员查询功能未配置 NESTJS_SERVICE_KEY,"
                "请提示管理员配置 ai-service 与 NestJS 的内部服务密钥后重启")
    headers = {
        "X-Service-Key": key,
        "X-User-Id": user_id,
        "Content-Type": "application/json",
    }
    try:
        # httpx 不能懒加载 async,同步工具里用同步客户端即可(查询轻量)
        resp = httpx.get(f"{base}/v1/users", headers=headers, timeout=10.0)
    except Exception as e:
        return f"成员查询出错:{e},请向用户说明情况"

    if resp.status_code != 200:
        return (f"成员查询失败(HTTP {resp.status_code}):"
                f"{resp.text[:200]}。请告知用户稍后重试")

    try:
        users = resp.json()
    except json.JSONDecodeError:
        return "成员查询返回格式异常,请告知用户稍后重试"

    if not isinstance(users, list):
        return "成员查询返回格式异常,请告知用户稍后重试"

    # 可选关键词过滤(用户名/显示名/部门名/职级名模糊匹配)
    if keyword:
        kw = keyword.strip().lower()
        users = [u for u in users if kw in (
            (u.get("username") or "").lower()
            or (u.get("displayName") or "").lower()
            or ((u.get("department") or {}).get("name") or "").lower()
            or ((u.get("jobLevel") or {}).get("name") or "").lower()
        )]
    if not users:
        return "未找到符合条件的团队成员。"

    lines = []
    for u in users:
        dept = (u.get("department") or {}).get("name") or "-"
        level = (u.get("jobLevel") or {}).get("name") or "-"
        position = u.get("deptPosition") or "-"
        name = u.get("displayName") or u.get("username") or "-"
        lines.append(f"- {name}({u.get('username')}) | 部门:{dept} | 职级:{level} | 职位:{position}")
    return "当前可见团队成员:\n" + "\n".join(lines)


def _fetch_job_levels(base: str, key: str, user_id: str, department_id: int | None = None) -> list[dict]:
    """调 NestJS GET /v1/job-levels 拉取职级列表(可按部门过滤),失败返回空列表。"""
    if not key:
        return []
    headers = {
        "X-Service-Key": key,
        "X-User-Id": user_id,
        "Content-Type": "application/json",
    }
    params = {}
    if department_id:
        params["departmentId"] = department_id
    try:
        resp = httpx.get(f"{base}/v1/job-levels", headers=headers, params=params, timeout=10.0)
    except Exception:
        return []
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    return data if isinstance(data, list) else []


def build_team_member_tool(user_id: str):
    """构造"调整团队成员职级"写工具,以发起请求的用户身份执行审批与落库。

    user_id: 请求该 Agent 会话的 NestJS 用户 id(UUID),审批通过后作为操作者
    透传给 NestJS,服务层据此校验"上级管下级"等授权规则。
    """
    base, key = _nestjs_env()

    def _human_summary(target_user_id, job_level_id, department_id, dept_position):
        lines = [f"目标用户: {target_user_id}"]
        if department_id:
            lines.append(f"转入部门: {department_id}")
        if job_level_id:
            lines.append(f"目标职级: {job_level_id}")
        if dept_position:
            lines.append(f"部门内职位: {dept_position}")
        lines.append(f"操作人: {user_id}")
        lines.append("权限影响: 随职级自动继承(变更后立即生效)")
        return "\n".join(lines)

    @tool
    async def adjust_team_member(
        target_user_id: str,
        job_level_id: int | None = None,
        department_id: int | None = None,
        dept_position: str | None = None,
    ) -> str:
        """调整团队成员的职级(可同时转岗/改部门内职位)。

        这是写操作,变更会记入审批卡片并等待用户确认后才执行。参数说明:
        target_user_id: 被调整成员的 NestJS 用户 id;job_level_id: 目标职级 id
        (按部门划分,须属于目标用户所在部门,给 id 即可);
        department_id: 可选,转入的部门 id(转岗);dept_position: 可选,部门内职位
        (manager/deputy/leader/member)。仅当用户明确要求调整某成员职级/转岗时调用,
        查询类提问不要调用。"""
        if not key:
            return ("成员调整功能未配置 NESTJS_SERVICE_KEY,"
                    "请提示管理员配置 ai-service 与 NestJS 的内部服务密钥后重启")

        # 拉取职级列表供前端审批卡片渲染下拉选择(按目标用户所在部门过滤)
        # 注意:这里无法预知目标用户部门,先拉全量;前端按 departmentId 过滤展示
        job_levels = _fetch_job_levels(base, key, user_id)

        # [1] 挂起等待人工审批:value 带待审批明细 + 职级选项列表
        decision = interrupt({
            "action": "调整团队成员职级",
            "detail": _human_summary(target_user_id, job_level_id,
                                     department_id, dept_position),
            "targetUserId": target_user_id,
            "jobLevelId": job_level_id,
            "departmentId": department_id,
            "deptPosition": dept_position,
            "operatorId": user_id,
            "jobLevels": job_levels,  # 前端渲染下拉选择用
        })

        # 决策可能是字符串(兼容旧逻辑)或 dict(新交互式审批)
        if isinstance(decision, str):
            # 旧逻辑兼容:resume 只传 decision 字符串
            if decision != "approve":
                return f"已拒绝该成员({target_user_id})的职级调整审批,未做任何变更。"
            final_job_level_id = job_level_id
            reason = ""
        else:
            # 新逻辑:resume 传 dict {decision, jobLevelId, reason}
            if decision.get("decision") != "approve":
                return f"已拒绝该成员({target_user_id})的职级调整审批,未做任何变更。"
            final_job_level_id = decision.get("jobLevelId") or job_level_id
            reason = decision.get("reason") or ""

        # [2] 审批通过:真正调 NestJS 落库(强制 confirm:true + X-HITL 审计)
        body = {"confirm": True}
        if final_job_level_id:
            body["jobLevelId"] = final_job_level_id
        if department_id:
            body["departmentId"] = department_id
        if dept_position:
            body["deptPosition"] = dept_position
        if reason:
            body["reason"] = reason

        headers = {
            "X-Service-Key": key,   # 与 NestJS jwt-auth.guard 的 NESTJS_SERVICE_KEY 同值
            "X-User-Id": user_id,   # 操作者 = 请求该 Agent 会话的用户
            "X-HITL": "approved",   # 写审计 outcome = approved(users.controller outcomeOf)
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                resp = await c.patch(
                    f"{base}/v1/users/{target_user_id}",
                    headers=headers,
                    json=body,
                )
        except Exception as e:
            # 返回可读错误让模型自行向用户解释,而不是让工具调用崩溃
            return f"审批已通过,但调用成员服务出错:{e},请向用户说明情况"

        if resp.status_code != 200:
            return (f"审批已通过,但提交失败(HTTP {resp.status_code}):"
                    f"{resp.text[:200]}。请向用户说明并稍后重试。")
        data = resp.json()
        level_name = (data.get('jobLevel') or {}).get('name')
        return (
            f"已完成对成员 {target_user_id} 的职级调整。"
            f"当前职级: {level_name} / "
            f"部门: {(data.get('department') or {}).get('name')} / "
            f"职位: {data.get('deptPosition')}。"
            f"{f' 理由: {reason}' if reason else ''}"
        )

    return adjust_team_member