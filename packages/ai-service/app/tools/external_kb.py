"""外部知识库检索工具(闭包注入用户与服务配置):
通过 rag-service 的 /api/rag/search 检索"外部挂载的内部知识库"文档片段。

区别于内嵌 RAG(search_docs,走 ai-service 自身的 documents/chunks):
本工具只在该 rag 独立成"外部挂载知识库"时由 Agent 按场景触发,
内部以 X-Service-Key / X-User-Id 调用 rag-service,拿回片段供 Agent 继续编排。
"""
import os

from langchain_core.tools import tool

_DEFAULT_DOC = """当用户的问题明确涉及"外部挂载的内部知识库 / 专属资料库"时调用,
传入检索问题,返回最相关的知识库文档片段。
普通聊天、常识问题、以及已在用户上传文档内的问题不要调用。"""


def build_external_kb_tool(user_id: str):
    rag_base = os.getenv("RAG_SERVICE_BASE_URL", "http://localhost:26016").rstrip("/")
    rag_key = os.getenv("RAG_SERVICE_KEY", "")

    @tool
    async def search_external_knowledge(question: str, knowledge_base_id: str = "") -> str:
        """当用户的问题涉及外部挂载的内部知识库/专属资料时调用。
        传入检索问题(question)与知识库 ID(knowledge_base_id,可选,
        缺省检索该用户全部知识库),返回最相关的文档片段。
        普通聊天、常识问题、已在上传文档内的问题不要调用。"""
        import httpx

        if not rag_key:
            return ("外部知识库未配置 RAG_SERVICE_KEY,"
                    "请提示管理员设置 rag-service / ai-service 的内部服务密钥后重启")
        payload = {"question": question, "knowledgeBaseId": knowledge_base_id}
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                resp = await c.post(
                    f"{rag_base}/api/rag/search",
                    headers={
                        "X-Service-Key": rag_key,
                        "X-User-Id": user_id,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            if resp.status_code != 200:
                return f"外部知识库查询失败(HTTP {resp.status_code}),请告知用户稍后重试"
            data = resp.json()
        except Exception as e:
            # 返回可读错误让模型自行向用户解释,而不是让工具调用崩溃
            return f"外部知识库查询出错:{e},请向用户说明情况"

        hits = data.get("data") or []
        if not hits:
            return "外部知识库中未找到相关内容,请基于自身知识回答并说明知识库中没有相关信息"
        return "\n\n---\n\n".join(
            f"[片段 {h.get('chunkIndex', i + 1)}] {h.get('content', '')}"
            for i, h in enumerate(hits)
        )

    return search_external_knowledge