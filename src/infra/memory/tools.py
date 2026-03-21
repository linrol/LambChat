"""
Unified Memory Tools - LangChain Tool Integration

Provides a single set of memory tools that work with any MemoryBackend.
The underlying backend is transparent to the Agent — tool names and interfaces
are identical regardless of which memory provider is active.
"""

import asyncio
import json
from typing import Annotated, Optional

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool

from src.infra.logging import get_logger
from src.infra.memory.client.base import MemoryBackend, create_memory_backend, is_memory_enabled
from src.infra.memory.client.hindsight import get_user_id_from_runtime

logger = get_logger(__name__)

# Module-level cached backend (initialized lazily)
_backend: Optional[MemoryBackend] = None
_backend_lock = asyncio.Lock()


async def _get_backend() -> Optional[MemoryBackend]:
    """Get or create the active memory backend (singleton)."""
    global _backend
    if _backend is not None:
        return _backend

    async with _backend_lock:
        if _backend is None:
            _backend = await create_memory_backend()
            if _backend is None:
                logger.debug("[Memory] No backend available")
        return _backend


# ============================================================================
# Unified Memory Tools
# ============================================================================


@tool
async def memory_retain(
    content: Annotated[str, "The memory content to store (facts, observations, experiences)"],
    context: Annotated[
        Optional[str],
        "Optional context or category for this memory (e.g., 'user_preferences', 'project_info')",
    ] = None,
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> str:
    """
    Store a memory for cross-session persistence.

    Use this tool to remember important information that should persist across
    different conversation sessions. Examples: user preferences, important facts,
    project details, user background, etc.
    """
    user_id = get_user_id_from_runtime(runtime)
    if not user_id:
        return json.dumps({"success": False, "error": "User not authenticated"}, ensure_ascii=False)

    backend = await _get_backend()
    if not backend:
        return json.dumps(
            {"success": False, "error": "Memory service not available"},
            ensure_ascii=False,
        )

    try:
        result = await backend.retain(user_id, content, context)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[Memory] Failed to retain memory: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
async def memory_recall(
    query: Annotated[str, "The search query to find relevant memories"],
    max_results: Annotated[int, "Maximum number of memories to return (default: 5)"] = 5,
    memory_types: Annotated[
        Optional[list[str]],
        "Filter by memory types (backend-specific), or None for all types",
    ] = None,
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> str:
    """
    Search and retrieve relevant memories from cross-session storage.

    Use this tool to recall previously stored information. The search is
    semantic and will find memories that are conceptually related to the query.
    """
    user_id = get_user_id_from_runtime(runtime)
    if not user_id:
        return json.dumps({"success": False, "error": "User not authenticated"}, ensure_ascii=False)

    backend = await _get_backend()
    if not backend:
        return json.dumps(
            {"success": False, "error": "Memory service not available"},
            ensure_ascii=False,
        )

    try:
        result = await backend.recall(user_id, query, max_results, memory_types)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[Memory] Failed to recall memories: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
async def memory_delete(
    memory_id: Annotated[str, "The ID of the memory to delete"],
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> str:
    """
    Delete a specific memory by ID.

    Use this tool when a user wants to remove a specific memory.
    Get the memory ID from the memory_recall tool output.
    """
    user_id = get_user_id_from_runtime(runtime)
    if not user_id:
        return json.dumps({"success": False, "error": "User not authenticated"}, ensure_ascii=False)

    backend = await _get_backend()
    if not backend:
        return json.dumps(
            {"success": False, "error": "Memory service not available"},
            ensure_ascii=False,
        )

    try:
        result = await backend.delete(user_id, memory_id)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[Memory] Failed to delete memory: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ============================================================================
# Tool Factory Functions
# ============================================================================


def get_memory_retain_tool() -> BaseTool:
    return memory_retain


def get_memory_recall_tool() -> BaseTool:
    return memory_recall


def get_memory_delete_tool() -> BaseTool:
    return memory_delete


def get_all_memory_tools() -> list[BaseTool]:
    """Get all unified memory tools (works with any backend)."""
    return [memory_retain, memory_recall, memory_delete]


# ============================================================================
# Unified Auto-Retention (Background Task)
# ============================================================================


async def auto_retain_conversation(
    user_id: str,
    conversation_summary: str,
    context: Optional[str] = None,
) -> None:
    """
    Automatically store conversation summary as memory (fire-and-forget).
    Dispatches to the active backend.
    """
    if not user_id or not conversation_summary:
        return

    try:
        backend = await _get_backend()
        if backend:
            await backend.auto_retain(user_id, conversation_summary, context)
            return

        logger.debug("[Memory] No backend enabled, skipping auto-retain")
    except Exception as e:
        logger.warning(f"[Memory] Auto-retain failed (non-critical): {e}")


def schedule_auto_retain(
    user_id: str,
    conversation_summary: str,
    context: Optional[str] = None,
) -> None:
    """
    Schedule auto-retention as a background task (fire-and-forget).
    Works with any backend.
    """
    if not is_memory_enabled():
        return

    if not user_id or not conversation_summary:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("[Memory] No running event loop, skipping auto-retain")
        return

    task = loop.create_task(
        auto_retain_conversation(
            user_id=user_id,
            conversation_summary=conversation_summary,
            context=context,
        )
    )
    task.add_done_callback(_background_task_error)


def _background_task_error(task: asyncio.Task) -> None:
    """Handle exceptions from background tasks."""
    try:
        exc = task.exception()
        if exc:
            logger.warning(f"[Memory] Background auto-retain task failed: {exc}")
    except asyncio.CancelledError:
        pass
