"""事件模型定义:prompteng / contexteng 共用的事件契约。

harness 钩子回调携带的 dict 结构在这里统一定义(TypedDict),
将来拆服务时这套结构即 HTTP 上报的 payload,钩子处零改动。
"""
from typing import TypedDict


class RetrievalEvent(TypedDict, total=False):
    """检索事件(search_docs 每次调用一条)"""
    user_id: str           # NestJS 用户 ID
    conversation_id: str   # 会话 ID(adhoc 模式为 "")
    query: str             # 模型自主生成的检索词
    strategy: str          # 检索策略标识
    top_k: int             # 请求的 top_k
    threshold: float       # 相似度阈值
    hits: list[dict]       # [{"chunk_id","doc_id","score","position"}],按分数降序
    hit_count: int         # 过阈值后的命中数
    max_score: float       # 最高相似度;零结果时为候选最高分
    latency_ms: int        # 检索耗时(含 embedding)


class ContextSnapshot(TypedDict, total=False):
    """Context 快照(每次模型决策调用一条)"""
    user_id: str
    conversation_id: str
    model: str             # 模型名
    total_tokens: int      # usage 精确值;未知 -1
    system_tokens: int     # 估算(len/1.6)
    history_tokens: int    # 估算
    tool_tokens: int       # 估算
    message_count: int
    rag_chunk_ids: list[str]
    rag_injected: int      # 1/0
    truncated: int         # 第一阶段恒 0
    latency_ms: int        # 模型调用耗时(pe_usage_events 用)


class PromptAssembly(TypedDict, total=False):
    """Prompt 装配完成事件(每次拼装系统提示词一条,轻量,默认只进内存)"""
    template_key: str      # 如 'agent.system'
    version: int           # 使用的模板版本;0 = 代码默认
    source: str            # 'db' / 'code'
    content_len: int       # 装配后字符数


class PromptUsageEvent(TypedDict, total=False):
    """Prompt 使用事件(每次模型调用一条,由 collector 从快照派生)"""
    template_key: str
    version: int
    user_id: str
    conversation_id: str
    prompt_tokens: int     # usage 精确值;未知 -1
    latency_ms: int
