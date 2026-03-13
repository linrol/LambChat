"""
OpenViking 上下文检索

每轮对话前从 OpenViking 检索相关上下文，以 L0 摘要注入用户消息。
Agent 可通过 read_knowledge 工具按需深入获取完整内容。
支持多轮上下文感知查询构建。
"""

import logging
from typing import Optional

from src.kernel.config import settings

logger = logging.getLogger(__name__)


def build_retrieval_query(
    current_input: str,
    recent_messages: Optional[list[dict]] = None,
) -> str:
    """
    构建更智能的检索查询。

    结合当前输入和最近 3 轮对话历史，提升检索相关性。
    """
    parts = []

    # 最近 3 轮历史（如果有）
    if recent_messages:
        for msg in recent_messages[-3:]:
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                # 截取前 200 字符避免查询过长
                parts.append(content[:200])

    # 当前输入放最后（权重最高）
    parts.append(current_input)

    return " ".join(parts)


async def retrieve_context(
    query: str,
    user_id: str,
    session_id: Optional[str] = None,
    limit: int = 5,
    recent_messages: Optional[list[dict]] = None,
) -> str:
    """
    从 OpenViking 检索相关上下文，返回格式化的 system prompt 片段。

    采用 L0 渐进式加载：仅注入摘要（abstract），Agent 可通过
    read_knowledge 工具按需深入获取完整内容，节省 token。
    """
    if not settings.ENABLE_OPENVIKING:
        return ""

    try:
        from src.infra.openviking.client import get_openviking_client

        client = await get_openviking_client()
        if client is None:
            return ""

        # 智能查询构建：结合历史上下文
        search_query = build_retrieval_query(query, recent_messages)

        results = await client.find(search_query, limit=limit)
        if not results:
            return ""

        return _format_context(results)

    except Exception as e:
        logger.warning("[OpenViking] Context retrieval failed: %s", e)
        return ""


def _format_context(results: list) -> str:
    """将检索结果格式化为 L0 摘要注入块。"""
    sections = []
    for item in results:
        if isinstance(item, dict):
            uri = item.get("uri", item.get("path", ""))
            abstract = item.get("abstract", item.get("content", ""))
            score = item.get("score", 0)
            try:
                score_str = f"{float(score):.2f}"
            except (TypeError, ValueError):
                score_str = str(score)
            sections.append(f"- [{uri}] (相关度: {score_str}): {abstract}")
        elif isinstance(item, str):
            sections.append(f"- {item}")

    if not sections:
        return ""

    header = "\n\n<memory_context>\n"
    header += "以下是与当前对话相关的记忆摘要。如需详细内容，使用 read_knowledge 工具。\n\n"
    body = "\n".join(sections)
    footer = "\n</memory_context>"

    return header + body + footer
