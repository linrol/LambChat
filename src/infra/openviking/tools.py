"""
OpenViking 记忆工具

提供 4 个 LangChain 工具，让 Agent 主动管理记忆：
- search_memory: 语义搜索记忆和知识库
- save_memory: 显式保存记忆笔记
- browse_memory: 浏览记忆树（L0 摘要）
- read_knowledge: 读取特定资源的完整内容
"""

import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool

from src.kernel.config import settings

logger = logging.getLogger(__name__)


async def _get_client():
    """获取 OpenViking root 客户端（仅用于管理操作）。"""
    from src.infra.openviking.client import get_openviking_client

    client = await get_openviking_client()
    if client is None:
        raise RuntimeError("OpenViking client not available")
    return client


async def _get_user_client(user_id: str):
    """
    获取用户的 OpenViking 客户端。

    自动确保用户账户存在，返回用户专属客户端。

    Args:
        user_id: 用户 ID

    Returns:
        OpenVikingClient 实例

    Raises:
        RuntimeError: 如果无法获取用户客户端
    """
    from src.infra.openviking.client import get_user_client
    from src.infra.openviking.user_manager import ensure_user_account

    success, api_key = await ensure_user_account(user_id)
    if not success or not api_key:
        raise RuntimeError(f"Failed to get OpenViking credentials for user: {user_id}")

    client = await get_user_client(user_id, api_key)
    if client is None:
        raise RuntimeError(f"Failed to create OpenViking client for user: {user_id}")
    return client


def _get_user_id(runtime: Optional[ToolRuntime]) -> str:
    """从 ToolRuntime 中提取 user_id。"""
    if runtime and hasattr(runtime, "config") and isinstance(runtime.config, dict):
        configurable = runtime.config.get("configurable", {})
        context = configurable.get("context")
        if context and hasattr(context, "user_id") and context.user_id:
            return context.user_id
    return "default"


def _format_find_results(results) -> list[str]:
    """将 FindResult 格式化为可读字符串列表。"""
    sections = []

    # FindResult 包含 memories, resources, skills 三个列表
    all_contexts: list[Any] = []
    if hasattr(results, "memories"):
        all_contexts.extend(results.memories or [])
    if hasattr(results, "resources"):
        all_contexts.extend(results.resources or [])
    if hasattr(results, "skills"):
        all_contexts.extend(results.skills or [])

    # 兼容旧格式（直接返回列表）
    if not all_contexts and isinstance(results, list):
        all_contexts = results

    for item in all_contexts:
        if hasattr(item, "uri"):
            # MatchedContext 对象
            uri = item.uri
            abstract = getattr(item, "abstract", "") or ""
            score = getattr(item, "score", 0) or 0
            context_type = getattr(item, "context_type", "unknown") or "unknown"
            try:
                score_str = f"{float(score):.2f}"
            except (TypeError, ValueError):
                score_str = str(score)
            type_label = f"[{context_type}] " if context_type != "unknown" else ""
            sections.append(f"{type_label}[{uri}] (相关度: {score_str})\n{abstract}")
        elif isinstance(item, dict):
            uri = item.get("uri", item.get("path", ""))
            abstract = item.get("abstract", item.get("content", ""))
            score = item.get("score", 0)
            try:
                score_str = f"{float(score):.2f}"
            except (TypeError, ValueError):
                score_str = str(score)
            sections.append(f"[{uri}] (相关度: {score_str})\n{abstract}")
        elif isinstance(item, str):
            sections.append(item)

    return sections


@tool
async def search_memory(
    query: str,
    limit: int = 5,
    scope: str = "all",
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> str:
    """搜索用户的记忆和知识库，返回与查询最相关的内容。

    当你需要回忆之前的对话、查找用户偏好、或检索相关知识时使用此工具。

    Args:
        query: 搜索查询，描述你想找的信息
        limit: 最大返回条数（默认 5）
        scope: 搜索范围 - "all"(全部)、"memories"(可写的用户记忆)、"auto_memories"(只读的自动提取记忆)、"skills"(技能)
    """
    if not settings.ENABLE_OPENVIKING:
        return "记忆系统未启用。"

    try:
        user_id = _get_user_id(runtime)
        client = await _get_user_client(user_id)

        # 根据 scope 确定 target_uri
        # memories: 可写路径（与 /memories/ backend 路由一致）
        # auto_memories: 只读路径（OpenViking 自动提取的记忆）
        from src.infra.openviking.user_manager import get_user_memory_uri, get_user_resource_uri

        scope_map = {
            "all": "",  # 搜索全部
            "memories": get_user_resource_uri(user_id),  # 可写的用户记忆
            "auto_memories": get_user_memory_uri(user_id),  # 只读的自动提取记忆
            "skills": "viking://agent/skills",
        }
        target_uri = scope_map.get(scope, "")

        results = await client.find(query, limit=limit, target_uri=target_uri)
        if not results:
            return f"未找到与 '{query}' 相关的记忆。"

        sections = _format_find_results(results)
        return "\n\n---\n\n".join(sections) if sections else "未找到相关记忆。"

    except Exception as e:
        logger.warning("[OpenViking] search_memory failed: %s", e)
        return f"记忆搜索失败: {e}"


@tool
async def save_memory(
    content: str,
    category: str = "general",
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> str:
    """将重要信息保存到用户的长期记忆中。

    当用户明确要求你记住某些信息，或你发现值得长期保存的关键信息时使用此工具。
    例如：用户偏好、重要决策、项目约定等。

    Args:
        content: 要保存的记忆内容
        category: 记忆分类（如 general, preference, decision, project）
    """
    if not settings.ENABLE_OPENVIKING:
        return "记忆系统未启用。"

    user_id = _get_user_id(runtime)
    from src.infra.openviking.user_manager import get_user_resource_uri

    # 目标 URI：viking://resources/users/{user_id}/memories/{category}/
    target_uri = f"{get_user_resource_uri(user_id).rstrip('/')}/{category}"

    try:
        client = await _get_user_client(user_id)

        # 使用临时文件保存文本内容，确保正确索引
        # add_resource 设计用于文件路径，直接传文本字符串可能导致索引问题
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name

        try:
            # 使用临时文件路径添加资源，wait=True 确保索引完成
            result = await client.add_resource(
                path=tmp_path,
                to=target_uri,
                reason=f"User memory saved via save_memory tool, category: {category}",
                wait=True,
            )
            logger.debug("[OpenViking] save_memory result: %s", result)
            return f"已保存到 {category} 分类。"
        finally:
            # 清理临时文件
            Path(tmp_path).unlink(missing_ok=True)

    except Exception as e:
        error_msg = str(e)
        logger.warning("[OpenViking] save_memory failed: %s", e)

        # 如果是 API Key 无效，尝试清除缓存并重试一次
        if "Invalid API Key" in error_msg or "api key" in error_msg.lower():
            logger.info("[OpenViking] Invalid API Key detected, clearing cache and retrying...")
            from src.infra.openviking.user_manager import invalidate_user_cache

            await invalidate_user_cache(user_id)
            try:
                client = await _get_user_client(user_id)

                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".md", delete=False, encoding="utf-8"
                ) as tmp_file:
                    tmp_file.write(content)
                    tmp_path = tmp_file.name

                try:
                    result = await client.add_resource(
                        path=tmp_path,
                        to=target_uri,
                        reason=f"User memory saved via save_memory tool, category: {category}",
                        wait=True,
                    )
                    logger.debug("[OpenViking] save_memory retry result: %s", result)
                    return f"已保存到 {category} 分类。"
                finally:
                    Path(tmp_path).unlink(missing_ok=True)
            except Exception as retry_error:
                logger.warning("[OpenViking] save_memory retry failed: %s", retry_error)
                return f"保存记忆失败: {retry_error}"

        return f"保存记忆失败: {e}"


@tool
async def browse_memory(
    path: str = "/",
    scope: str = "memories",
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> str:
    """浏览用户的记忆树结构，查看有哪些记忆和知识资源。

    返回指定路径下的目录和文件列表（含 L0 摘要）。
    先用此工具了解记忆结构，再用 read_knowledge 读取具体内容。

    Args:
        path: 要浏览的路径（默认根目录 "/"，相对于 scope 基础路径）
        scope: 浏览范围 - "memories"(可写的用户记忆) 或 "auto_memories"(只读的自动提取记忆)
    """
    if not settings.ENABLE_OPENVIKING:
        return "记忆系统未启用。"

    try:
        user_id = _get_user_id(runtime)
        client = await _get_user_client(user_id)

        # 根据 scope 选择基础路径
        # memories: 可写路径（与 /memories/ backend 路由一致）
        # auto_memories: 只读路径（OpenViking 自动提取的记忆）
        from src.infra.openviking.user_manager import get_user_memory_uri, get_user_resource_uri

        if scope == "auto_memories":
            base = get_user_memory_uri(user_id).rstrip("/")  # viking://user/{user_id}/memories
        else:
            # 默认使用可写路径（与 backend /memories/ 路由一致）
            base = get_user_resource_uri(user_id).rstrip(
                "/"
            )  # viking://resources/users/{user_id}/memories

        clean_path = path.strip("/")
        uri = f"{base}/{clean_path}" if clean_path else base

        items = await client.ls(uri, simple=True)
        if not items:
            return f"路径 {path} 下没有内容。"

        lines = []
        for item in items:
            if isinstance(item, dict):
                name = item.get("name", item.get("uri", ""))
                is_dir = item.get("is_dir", name.endswith("/") if name else False)
                abstract = item.get("abstract", "")
                prefix = "[DIR] " if is_dir else "[FILE]"
                line = f"{prefix} {name}"
                if abstract:
                    line += f"\n  → {abstract}"
                lines.append(line)
            elif isinstance(item, str):
                lines.append(f"  {item}")

        return "\n".join(lines) if lines else "目录为空。"

    except Exception as e:
        logger.warning("[OpenViking] browse_memory failed: %s", e)
        return f"浏览记忆失败: {e}"


@tool
async def read_knowledge(
    uri: str,
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> str:
    """读取特定记忆或知识资源的完整内容。

    当 search_memory 或 browse_memory 返回了感兴趣的 URI 后，
    使用此工具获取该资源的完整内容。

    Args:
        uri: 资源的 URI（如 viking://user/xxx/memories/general）
    """
    if not settings.ENABLE_OPENVIKING:
        return "记忆系统未启用。"

    try:
        user_id = _get_user_id(runtime)
        client = await _get_user_client(user_id)
        content = await client.read(uri)
        if not content:
            return f"未找到内容: {uri}"
        return content

    except Exception as e:
        logger.warning("[OpenViking] read_knowledge failed: %s", e)
        return f"读取失败: {e}"


def get_openviking_tools() -> list[BaseTool]:
    """获取所有 OpenViking 记忆工具。"""
    if not settings.ENABLE_OPENVIKING:
        return []
    return [search_memory, save_memory, browse_memory, read_knowledge]
