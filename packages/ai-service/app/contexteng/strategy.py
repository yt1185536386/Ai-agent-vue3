"""检索策略对象:rag.py 切分/相似度参数的唯一来源(被调优对象)。

策略由 contexteng 维护:启动时从环境变量初始化,运行期可经 API 调整;
每次检索事件记录 strategy 标识,同一时段不同策略的指标可分组对比
(A/B 的基础)。重建索引(按新策略重切)走 /v1/documents/rebuild。
"""
import os

# 内存策略对象:strategy 标识 + 切分/检索参数
_STRATEGY: dict = {
    "strategy": os.getenv("RAG_STRATEGY", "chunk600_ov80_cosine"),
    "size": int(os.getenv("RAG_CHUNK_SIZE", "600")),
    "overlap": int(os.getenv("RAG_CHUNK_OVERLAP", "80")),
    "top_k": int(os.getenv("RAG_TOP_K", "3")),
    "threshold": float(os.getenv("RAG_THRESHOLD", "0.3")),
}


def current() -> dict:
    """当前生效策略(拷贝);rag.py / tools/rag.py 每次调用现读,支持热切换"""
    return dict(_STRATEGY)


def update(**kwargs) -> dict:
    """调整策略参数(API 用);strategy 标识未显式给出时按参数自动生成"""
    for k in ("size", "overlap", "top_k"):
        if k in kwargs and kwargs[k] is not None:
            _STRATEGY[k] = int(kwargs[k])
    if kwargs.get("threshold") is not None:
        _STRATEGY["threshold"] = float(kwargs["threshold"])
    if kwargs.get("strategy"):
        _STRATEGY["strategy"] = str(kwargs["strategy"])
    else:
        _STRATEGY["strategy"] = (
            f"chunk{_STRATEGY['size']}_ov{_STRATEGY['overlap']}_cosine")
    return current()
