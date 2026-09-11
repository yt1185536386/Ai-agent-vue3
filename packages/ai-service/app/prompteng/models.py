"""pe_* 表:Prompt 模板 / 版本 / 使用事件 / 日聚合。

命名规范:pe_<实体>[_<用途后缀>];零跨域外键(template_key、conversation_id
等只作逻辑关联,不建 FK)。所有表/列带注释,便于将来拆库拆服务。
"""
from datetime import datetime

from sqlalchemy import (
    DateTime, Float, ForeignKey, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PeTemplate(Base):
    """Prompt 模板主表"""

    __tablename__ = "pe_templates"
    __table_args__ = {"comment": "Prompt 模板主表:key 为代码引用标识,版本在子表"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="模板 ID(uuid hex)")
    key: Mapped[str] = mapped_column(
        String(64), unique=True, index=True,
        comment="模板标识,代码中引用用,如 'agent.system'、'rag.search_docs'")
    name: Mapped[str] = mapped_column(String(100), comment="展示名,如「Agent 系统提示词」")
    group: Mapped[str] = mapped_column(
        "group", String(32), index=True,
        comment="模板分组:system / tool / judge / other")
    description: Mapped[str] = mapped_column(
        String(500), default="", comment="模板用途、影响面说明")
    status: Mapped[str] = mapped_column(
        String(16), default="active",
        comment="状态:active / disabled(disabled 时回退代码内默认)")
    current_version: Mapped[int] = mapped_column(
        default=0, comment="当前激活版本号,冗余便于查询;0 表示尚无激活版本")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, comment="UTC 创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
        comment="UTC 最近修改时间")


class PeTemplateVersion(Base):
    """模板版本表:每次修改产生新版本,不原地改"""

    __tablename__ = "pe_template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_pe_tpl_ver"),
        {"comment": "Prompt 模板版本表:版本号模板内单调递增,同一时刻仅一个 active"},
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="版本记录 ID(uuid hex)")
    template_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("pe_templates.id", ondelete="CASCADE"), index=True,
        comment="所属模板(域内唯一 FK)")
    version: Mapped[int] = mapped_column(comment="版本号,模板内单调递增")
    content: Mapped[str] = mapped_column(Text, comment="模板文本,变量用 {{var}} 占位")
    variables: Mapped[str] = mapped_column(
        Text, default="[]",
        comment='变量说明 JSON:[{"name":"rules","desc":"业务规则块","required":true}]')
    status: Mapped[str] = mapped_column(
        String(16), default="draft",
        comment="draft / active / archived;同一模板同一时刻仅一个 active")
    note: Mapped[str] = mapped_column(
        String(500), default="", comment="版本变更说明(改了什么、为什么)")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, comment="UTC 创建时间")


class PeUsageEvent(Base):
    """Prompt 使用事件流水:每次模型调用一条"""

    __tablename__ = "pe_usage_events"
    __table_args__ = {"comment": "Prompt 使用事件流水:按版本归因监控的关键"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="事件 ID(uuid hex)")
    template_key: Mapped[str] = mapped_column(
        String(64), index=True, comment="对应 pe_templates.key,逻辑关联不建 FK")
    version: Mapped[int] = mapped_column(
        default=0, comment="本次实际使用的版本号;0 表示代码内默认(无 DB 模板)")
    conversation_id: Mapped[str] = mapped_column(
        String(64), index=True, default="", comment="会话 ID,逻辑关联 conversations.id")
    user_id: Mapped[str] = mapped_column(
        String(64), index=True, default="",
        comment="NestJS 用户 ID,逻辑关联不建 FK")
    prompt_tokens: Mapped[int] = mapped_column(
        default=-1, comment="本次 prompt 部分 token 数;取自模型 usage,缺失时 -1 表示未知")
    latency_ms: Mapped[int] = mapped_column(default=0, comment="模型调用耗时(毫秒)")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, comment="UTC 事件时间")


class PeMetricsDaily(Base):
    """Prompt 指标日聚合(查询时惰性聚合 / eval 上报写入)"""

    __tablename__ = "pe_metrics_daily"
    __table_args__ = {"comment": "Prompt 指标日聚合:按 天 × 模板 × 版本 统计"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="记录 ID(uuid hex)")
    stat_date: Mapped[str] = mapped_column(
        String(10), index=True, comment="统计日,格式 YYYY-MM-DD(本地时区)")
    template_key: Mapped[str] = mapped_column(String(64), index=True, comment="模板标识")
    version: Mapped[int] = mapped_column(default=0, comment="版本号;0 表示「全部版本合计」行")
    call_count: Mapped[int] = mapped_column(default=0, comment="当日调用次数")
    avg_prompt_tokens: Mapped[float] = mapped_column(
        Float, default=0.0, comment="平均 prompt token(剔除 -1 未知值)")
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, comment="平均耗时(毫秒)")
    eval_pass_rate: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="当日最近一次回归评测通过率(0-1);未跑评测为 NULL")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, comment="UTC 入库时间")
