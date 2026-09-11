"""Prompt 模板种子脚本。

为 RAG / Context 工程创建计划约定的标准模板(agent.system / rag.search_docs)。
已存在的实验性模板不动,仅补充缺失的标准 key。
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv(".env")

from app.core.db import init_db, sessionmaker
from app.prompteng import service


AGENT_SYSTEM_TEMPLATE = """当前真实时间:{{time}}

{{rules}}

你是一位有帮助的 AI 助手。回答用户问题时,如果问题可能涉及其上传过的文档资料,请先调用 search_docs 工具检索相关片段,再基于检索结果作答。"""

RAG_SEARCH_DOCS_TEMPLATE = """当用户的问题可能涉及其上传过的文档资料时调用,
传入检索关键词,返回最相关的文档片段。
闲聊、常识问题、与文档无关的问题不要调用。"""


async def seed():
    init_db(os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./ai_service.db"))
    async with sessionmaker()() as s:
        for key, name, group, content in [
            ("agent.system", "Agent 系统提示词", "system", AGENT_SYSTEM_TEMPLATE),
            ("rag.search_docs", "RAG 检索工具描述", "tool", RAG_SEARCH_DOCS_TEMPLATE),
        ]:
            try:
                await service.create_template(
                    s, key=key, name=name, group=group,
                    description=f"{name}({key})",
                    content=content, note="标准模板种子",
                )
                await service.activate(s, key, 1)
                print(f"创建并激活模板: {key}")
            except ValueError:
                # key 已存在,仅刷新缓存
                print(f"模板已存在,跳过创建: {key}")
        await service.refresh_cache()


if __name__ == "__main__":
    asyncio.run(seed())
