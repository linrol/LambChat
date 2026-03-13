"""
OpenViking 上下文检索

每轮对话前从 OpenViking 检索相关上下文，以 L0 摘要注入用户消息。
Agent 可通过 read_knowledge 工具按需深入获取完整内容。

改进：
- 使用 search() 替代 find()，利用 session context 做意图分析
- 传递 ov_session_id 让检索更智能
- 跨 session 记忆通过 user_id 隔离
"""

import logging
from typing import Any, Optional

from src.kernel.config import settings

logger = logging.getLogger(__name__)


async def retrieve_context(
    query: str,
    user_id: str,
    ov_session_id: Optional[str] = None,
    limit: int = 5,
) -> str:
    """
    从 OpenViking 检索相关上下文，返回格式化的 prompt 片段。

    采用 L0 渐进式加载：仅注入摘要（abstract），Agent 可通过
    read_knowledge 工具按需深入获取完整内容，节省 token。

    Args:
        query: 用户输入
        user_id: 用户 ID，用于检索用户级别的记忆
        ov_session_id: OpenViking session ID，用于上下文感知检索
        limit: 返回结果数量限制

    Returns:
        格式化的上下文字符串，用于注入到 prompt
    """
    if not settings.ENABLE_OPENVIKING:
        return ""

    try:
        from src.infra.openviking.client import get_openviking_client

        client = await get_openviking_client()
        if client is None:
            return ""

        # 使用 search() 做智能检索（如果 session 可用）
        if ov_session_id and hasattr(client, "search"):
            # 带 session context 的智能检索
            results = await client.search(
                query=query,
                session_id=ov_session_id,
                limit=limit,
            )
        else:
            # 回退到 find()（无 session context）
            # 搜索用户的 memories 和 resources
            target_uri = f"viking://user/{user_id}/memories/"
            results = await client.find(query, limit=limit, target_uri=target_uri)

            # 如果没找到，尝试搜索 resources
            if not results or not _has_content(results):
                target_uri = f"viking://resources/users/{user_id}/"
                results = await client.find(query, limit=limit, target_uri=target_uri)

        if not results or not _has_content(results):
            return ""

        return _format_context(results)

    except Exception as e:
        logger.warning("[OpenViking] Context retrieval failed: %s", e)
        return ""


def _has_content(results) -> bool:
    """检查检索结果是否有内容。"""
    if hasattr(results, "memories"):
        return bool(results.memories or results.resources or results.skills)
    return bool(results)


def _extract_contexts(results) -> list:
    """从 FindResult 或列表中提取所有 context 对象。"""
    all_contexts: list[Any] = []

    # FindResult 包含 memories, resources, skills 三个列表
    if hasattr(results, "memories"):
        all_contexts.extend(results.memories or [])
    if hasattr(results, "resources"):
        all_contexts.extend(results.resources or [])
    if hasattr(results, "skills"):
        all_contexts.extend(results.skills or [])

    # 兼容旧格式（直接返回列表）
    if not all_contexts and isinstance(results, list):
        all_contexts = results

    return all_contexts


def _format_context(results) -> str:
    """将检索结果格式化为 L0 摘要注入块。"""
    all_contexts = _extract_contexts(results)

    sections = []
    for item in all_contexts:
        if hasattr(item, "uri"):
            # MatchedContext 对象
            uri = item.uri
            abstract = getattr(item, "abstract", "") or ""
            score = getattr(item, "score", 0) or 0
            try:
                score_str = f"{float(score):.2f}"
            except (TypeError, ValueError):
                score_str = str(score)
            sections.append(f"- [{uri}] (相关度: {score_str}): {abstract}")
        elif isinstance(item, dict):
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
