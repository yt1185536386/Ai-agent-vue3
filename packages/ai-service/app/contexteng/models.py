"""cx_* 表:检索事件 / context 快照 / 评测用例 / 日聚合。

命名规范:cx_<实体>[_<用途后缀>];chunk_id、conversation_id 等只作逻辑
记录,不建 FK(拆库拆服务前提)。所有表/列带注释。
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CxRetrievalEvent(Base):
    """检索事件流水:search_docs 每次调用一条"""

    __tablename__ = "cx_retrieval_events"
    __table_args__ = {"comment": "检索事件流水:RAG 召回质量观测的事实表"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="事件 ID(uuid hex)")
    user_id: Mapped[str] = mapped_column(
        String(64), index=True, default="", comment="NestJS 用户 ID,逻辑关联不建 FK")
    conversation_id: Mapped[str] = mapped_column(
        String(64), index=True, default="", comment="会话 ID,逻辑关联 conversations.id")
    query: Mapped[str] = mapped_column(
        Text, comment="检索 query(模型自主生成的检索词,非用户原文)")
    strategy: Mapped[str] = mapped_column(
        String(64), default="", comment="检索策略标识,如 'chunk600_ov80_cosine',调参实验分组用")
    top_k: Mapped[int] = mapped_column(default=0, comment="请求的 top_k")
    threshold: Mapped[float] = mapped_column(Float, default=0.0, comment="相似度阈值")
    hits: Mapped[str] = mapped_column(
        Text, default="[]",
        comment='命中明细 JSON:[{"chunk_id","doc_id","score","position"}],按分数降序')
    hit_count: Mapped[int] = mapped_column(default=0, comment="过阈值后的命中数;0 即零结果事件")
    max_score: Mapped[float] = mapped_column(
        Float, default=0.0, comment="最高相似度;零结果时为候选最高分(便于分析阈值合理性)")
    latency_ms: Mapped[int] = mapped_column(default=0, comment="检索耗时(含 embedding,毫秒)")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, comment="UTC 事件时间")


class CxContextSnapshot(Base):
    """Context 快照:每次模型决策调用一条,context 监控的核心"""

    __tablename__ = "cx_context_snapshots"
    __table_args__ = {"comment": "Context 快照:每次模型调用记录 context 构成与水位"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="快照 ID(uuid hex)")
    conversation_id: Mapped[str] = mapped_column(
        String(64), index=True, default="", comment="会话 ID,逻辑关联 conversations.id")
    user_id: Mapped[str] = mapped_column(
        String(64), index=True, default="", comment="NestJS 用户 ID,逻辑关联不建 FK")
    model: Mapped[str] = mapped_column(String(64), default="", comment="本次调用的模型名")
    total_tokens: Mapped[int] = mapped_column(
        default=-1, comment="本次发送的总 prompt token(取 usage;未知 -1)")
    system_tokens: Mapped[int] = mapped_column(
        default=0, comment="系统提示词部分 token(估算值:len(text)/1.6,非精确分词)")
    history_tokens: Mapped[int] = mapped_column(
        default=0, comment="对话历史部分 token(估算值:len(text)/1.6,非精确分词)")
    tool_tokens: Mapped[int] = mapped_column(
        default=0, comment="工具结果消息部分 token(估算值:len(text)/1.6,非精确分词)")
    message_count: Mapped[int] = mapped_column(default=0, comment="发送的消息总条数(含 system)")
    rag_chunk_ids: Mapped[str] = mapped_column(
        Text, default="[]", comment="本会话最近检索注入的 chunk_id 列表 JSON;无注入为 '[]'")
    rag_injected: Mapped[int] = mapped_column(
        default=0, comment="本轮 context 是否含检索内容:1 是 0 否")
    truncated: Mapped[int] = mapped_column(
        default=0, comment="是否发生裁剪:1 是 0 否;第一阶段恒 0(干预能力上线前预留)")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, comment="UTC 快照时间")


class CxEvalCase(Base):
    """检索评测用例(ground truth,支持线上回收)"""

    __tablename__ = "cx_eval_cases"
    __table_args__ = {"comment": "检索评测用例:Recall@K / Precision@K 的 ground truth"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="用例 ID(uuid hex)")
    query: Mapped[str] = mapped_column(Text, comment="评测问题")
    expect_doc_ids: Mapped[str] = mapped_column(
        Text, default="[]", comment="应命中的文档 ID 列表 JSON(逻辑关联 documents.id,不建 FK)")
    expect_contains: Mapped[str] = mapped_column(
        Text, default="[]", comment="命中 chunk 应包含的关键短语列表 JSON(内容级断言)")
    source: Mapped[str] = mapped_column(
        String(16), default="manual",
        comment="用例来源:manual(人工标注)/ online(线上零结果或低分 query 回收)")
    status: Mapped[str] = mapped_column(String(16), default="enabled", comment="enabled / disabled")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, comment="UTC 创建时间")


class CxMetricsDaily(Base):
    """Context 指标日聚合"""

    __tablename__ = "cx_metrics_daily"
    __table_args__ = {"comment": "Context 指标日聚合:检索质量与 context 水位按天统计"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="记录 ID(uuid hex)")
    stat_date: Mapped[str] = mapped_column(
        String(10), index=True, comment="统计日,格式 YYYY-MM-DD(本地时区)")
    retrieval_count: Mapped[int] = mapped_column(default=0, comment="当日检索调用次数")
    zero_result_rate: Mapped[float] = mapped_column(
        Float, default=0.0, comment="零结果率 = 零结果事件数 / 检索总数(0-1)")
    avg_max_score: Mapped[float] = mapped_column(Float, default=0.0, comment="平均最高相似度(0-1)")
    avg_hit_count: Mapped[float] = mapped_column(Float, default=0.0, comment="平均命中 chunk 数")
    rag_inject_rate: Mapped[float] = mapped_column(
        Float, default=0.0, comment="含检索注入的 context 占比(0-1)")
    avg_context_tokens: Mapped[float] = mapped_column(
        Float, default=0.0, comment="平均 context 总 token(剔除 -1 未知值)")
    p95_context_tokens: Mapped[int] = mapped_column(
        default=0, comment="context token 的 p95(剔除 -1 未知值)")
    recall_at_k: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="当日最近一次离线评测 Recall@K;未跑为 NULL")
    precision_at_k: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="当日最近一次离线评测 Precision@K;未跑为 NULL")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, comment="UTC 入库时间")
