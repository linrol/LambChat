"""
Hindsight Memory Service - Cross-session Long-term Memory

Provides integration with Hindsight API for persistent, cross-session memory storage.
Uses a shared Hindsight server with bank_id isolation for multi-tenancy.

Documentation: https://docs.hindsight.ai
"""

import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any, Optional

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool

from src.kernel.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# Concurrency Configuration
# ============================================================================

# Thread pool size - configurable via environment variable
_MAX_WORKERS = int(os.getenv("HINDSIGHT_MAX_WORKERS", "32"))

# Max concurrent API calls - prevents overwhelming the service
_MAX_CONCURRENT_REQUESTS = int(os.getenv("HINDSIGHT_MAX_CONCURRENT", "64"))

# Thread pool for blocking Hindsight client calls
_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="hindsight-")

# Lazily initialized concurrency primitives (must be created within an event loop)
_request_semaphore: Optional[asyncio.Semaphore] = None
_client_lock: Optional[asyncio.Lock] = None


def _get_request_semaphore() -> asyncio.Semaphore:
    """Get or create the request semaphore (lazy initialization)."""
    global _request_semaphore
    if _request_semaphore is None:
        _request_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_REQUESTS)
    return _request_semaphore


def _get_client_lock() -> asyncio.Lock:
    """Get or create the client lock (lazy initialization)."""
    global _client_lock
    if _client_lock is None:
        _client_lock = asyncio.Lock()
    return _client_lock


# Global shared client
_shared_client: Optional[Any] = None


async def get_hindsight_client() -> Optional[Any]:
    """
    Get or create the shared Hindsight client (thread-safe async singleton).

    Uses a single shared HindsightClient connected to a Hindsight server.
    Multi-tenancy is achieved through bank_id isolation (each user gets unique banks).

    Returns:
        HindsightClient instance or None if not configured
    """
    global _shared_client

    # Fast path: return cached client without lock
    if _shared_client is not None:
        return _shared_client

    if not settings.HINDSIGHT_ENABLED:
        logger.debug("[Hindsight] Hindsight is disabled")
        return None

    if not settings.HINDSIGHT_BASE_URL:
        logger.warning("[Hindsight] HINDSIGHT_BASE_URL not configured")
        return None

    # Thread-safe initialization with lock
    async with _get_client_lock():
        # Double-check after acquiring lock
        if _shared_client is not None:
            return _shared_client

        try:
            # Lazy import to avoid startup dependency
            from hindsight_client import Hindsight

            # Create shared client connected to Hindsight server
            _shared_client = Hindsight(
                base_url=settings.HINDSIGHT_BASE_URL,
                api_key=settings.HINDSIGHT_API_KEY or None,
                timeout=30.0,
            )

            logger.info(
                f"[Hindsight] Created shared client for server: {settings.HINDSIGHT_BASE_URL}"
            )
            return _shared_client

        except ImportError:
            logger.warning(
                "[Hindsight] hindsight-client package not installed. "
                "Install with: pip install hindsight-client"
            )
            return None
        except Exception as e:
            logger.error(f"[Hindsight] Failed to create client: {e}")
            return None


def get_hindsight_client_sync() -> Optional[Any]:
    """
    Get the cached Hindsight client synchronously (for non-async contexts).

    This only returns the cached client and does NOT initialize it.
    Use get_hindsight_client() for initialization.
    """
    return _shared_client


def get_user_id_from_runtime(runtime: Optional[ToolRuntime]) -> Optional[str]:
    """Extract user_id from ToolRuntime context."""
    if not runtime:
        return None

    try:
        if hasattr(runtime, "config"):
            config = runtime.config
            if isinstance(config, dict):
                configurable = config.get("configurable", {})
                context = configurable.get("context")
                if context and hasattr(context, "user_id"):
                    return context.user_id
    except Exception as e:
        logger.debug(f"[Hindsight] Failed to get user_id from runtime: {e}")

    return None


def _get_bank_id(user_id: str, bank_name: Optional[str] = None) -> str:
    """
    Generate bank ID for user isolation.

    Each user gets isolated memory banks identified by their user_id.
    Bank names allow organizing memories within a user's scope.

    Args:
        user_id: User identifier for multi-tenant isolation
        bank_name: Optional custom bank name for organizing memories

    Returns:
        Bank ID string (format: "user-{user_id}" or "user-{user_id}-{bank_name}")
    """
    # Base bank ID with user isolation
    base_id = f"user-{user_id}"

    if bank_name:
        # Sanitize bank name (alphanumeric, hyphens, underscores only)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in bank_name)
        return f"{base_id}-{safe_name}"

    return base_id


def _ensure_bank_exists(client: Any, bank_id: str, bank_name: Optional[str] = None) -> bool:
    """
    Ensure a memory bank exists, creating it if necessary.

    Args:
        client: Hindsight client
        bank_id: Bank identifier
        bank_name: Human-readable bank name

    Returns:
        True if bank exists or was created, False on error
    """
    try:
        client.create_bank(
            bank_id=bank_id,
            name=f"{bank_name or 'Default'} Memory Bank",
            mission="Store and retrieve user memories for cross-session persistence",
        )
        return True
    except Exception:
        # Bank likely already exists
        return True


async def _run_sync(func: Any, *args: Any, **kwargs: Any) -> Any:
    """
    Run a synchronous function in a thread pool to avoid blocking the event loop.

    This is necessary because the Hindsight client uses synchronous HTTP calls
    that may internally use asyncio, which conflicts with the running event loop.

    Includes semaphore limiting to prevent overwhelming the service.
    """
    async with _get_request_semaphore():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, lambda: func(*args, **kwargs))


async def _run_sync_with_retry(
    func: Any,
    *args: Any,
    max_retries: int = 3,
    retry_delay: float = 0.5,
    **kwargs: Any,
) -> Any:
    """
    Run a synchronous function with retry logic for transient failures.

    Args:
        func: The function to run
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries (exponential backoff)
        **kwargs: Arguments to pass to the function
    """
    import random

    last_error: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return await _run_sync(func, *args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                # Exponential backoff with jitter
                delay = retry_delay * (2**attempt) + random.uniform(0, 0.1)
                logger.warning(
                    f"[Hindsight] Retry {attempt + 1}/{max_retries} after error: {e}. "
                    f"Waiting {delay:.2f}s"
                )
                await asyncio.sleep(delay)

    if last_error is None:
        raise RuntimeError("Unexpected state: no error captured after retry loop")
    raise last_error


# ============================================================================
# Memory Tools
# ============================================================================


@tool
async def memory_retain(
    content: Annotated[str, "The memory content to store (facts, observations, experiences)"],
    context: Annotated[
        Optional[str],
        "Optional context or category for this memory (e.g., 'user_preferences', 'project_info')",
    ] = None,
    bank_name: Annotated[
        Optional[str], "Optional bank name for organizing memories (default: 'default')"
    ] = None,
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> str:
    """
    Store a memory for cross-session persistence.

    Use this tool to remember important information that should persist across
    different conversation sessions. Examples: user preferences, important facts,
    project details, user background, etc.

    The memory will be intelligently processed and categorized by Hindsight.
    """
    user_id = get_user_id_from_runtime(runtime)
    if not user_id:
        return json.dumps({"success": False, "error": "User not authenticated"}, ensure_ascii=False)

    client = await get_hindsight_client()
    if not client:
        return json.dumps(
            {"success": False, "error": "Memory service not available"},
            ensure_ascii=False,
        )

    try:
        bank_id = _get_bank_id(user_id, bank_name)

        # Ensure bank exists (with retry for transient failures)
        await _run_sync_with_retry(_ensure_bank_exists, client, bank_id, bank_name)

        # Retain the memory (with retry for transient failures)
        await _run_sync_with_retry(
            client.retain,
            bank_id=bank_id,
            content=content,
            context=context,
        )

        logger.info(f"[Hindsight] Retained memory for user {user_id}: {content}...")

        return json.dumps(
            {
                "success": True,
                "message": "Memory stored successfully",
                "content_preview": content,
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"[Hindsight] Failed to retain memory: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
async def memory_recall(
    query: Annotated[str, "The search query to find relevant memories"],
    bank_name: Annotated[
        Optional[str],
        "Optional bank name to search in (default: searches default bank)",
    ] = None,
    max_results: Annotated[int, "Maximum number of memories to return (default: 5)"] = 5,
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> str:
    """
    Search and retrieve relevant memories from cross-session storage.

    Use this tool to recall previously stored information. The search is
    semantic and will find memories that are conceptually related to the query,
    even if they don't contain exact keyword matches.

    Returns a list of relevant memories with their content and types.
    """
    user_id = get_user_id_from_runtime(runtime)
    if not user_id:
        return json.dumps({"success": False, "error": "User not authenticated"}, ensure_ascii=False)

    client = await get_hindsight_client()
    if not client:
        return json.dumps(
            {"success": False, "error": "Memory service not available"},
            ensure_ascii=False,
        )

    try:
        bank_id = _get_bank_id(user_id, bank_name)

        # Recall memories (with retry for transient failures)
        results = await _run_sync_with_retry(
            client.recall,
            bank_id=bank_id,
            query=query,
            max_tokens=4096,
            budget="mid",
        )

        memories = []
        for r in results.results[:max_results]:
            memory_item = {
                "text": r.text,
                "type": getattr(r, "type", "unknown"),
            }
            # Include chunks if available
            if hasattr(r, "chunks") and r.chunks:
                memory_item["source"] = r.chunks[0].text if r.chunks[0].text else None
            memories.append(memory_item)

        logger.info(f"[Hindsight] Recalled {len(memories)} memories for user {user_id}")

        return json.dumps(
            {
                "success": True,
                "query": query,
                "memories": memories,
                "total_found": len(results.results),
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"[Hindsight] Failed to recall memories: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
async def memory_reflect(
    query: Annotated[str, "The question or topic to reflect on using stored memories"],
    bank_name: Annotated[
        Optional[str], "Optional bank name to use (default: uses default bank)"
    ] = None,
    context: Annotated[
        Optional[str],
        "Optional context to guide the reflection (e.g., 'preparing for a meeting')",
    ] = None,
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> str:
    """
    Generate a response by reflecting on stored memories.

    Use this tool when you need to synthesize information from memories to
    answer a question or provide insights. This combines memory retrieval
    with intelligent response generation.

    Unlike recall (which returns raw memories), reflect generates a thoughtful
    response based on the user's memory history.
    """
    user_id = get_user_id_from_runtime(runtime)
    if not user_id:
        return json.dumps({"success": False, "error": "User not authenticated"}, ensure_ascii=False)

    client = await get_hindsight_client()
    if not client:
        return json.dumps(
            {"success": False, "error": "Memory service not available"},
            ensure_ascii=False,
        )

    try:
        bank_id = _get_bank_id(user_id, bank_name)

        # Reflect on memories (with retry for transient failures)
        answer = await _run_sync_with_retry(
            client.reflect,
            bank_id=bank_id,
            query=query,
            context=context,
            budget="mid",
        )

        logger.info(f"[Hindsight] Reflected on query for user {user_id}: {query}...")

        return json.dumps(
            {
                "success": True,
                "response": answer.text,
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"[Hindsight] Failed to reflect: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
async def memory_list(
    bank_name: Annotated[
        Optional[str], "Optional bank name to list memories from (default: 'default')"
    ] = None,
    memory_type: Annotated[
        Optional[str],
        "Filter by memory type: 'world' (facts), 'observation' (events), 'experience' (interactions), or None for all",
    ] = None,
    limit: Annotated[int, "Maximum number of memories to return (default: 20)"] = 20,
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> str:
    """
    List stored memories with optional filtering.

    Use this tool to browse through stored memories. You can filter by
    memory type to see specific categories:
    - 'world': Factual knowledge about the world/user
    - 'observation': Specific events or observations
    - 'experience': Past interactions and experiences
    """
    user_id = get_user_id_from_runtime(runtime)
    if not user_id:
        return json.dumps({"success": False, "error": "User not authenticated"}, ensure_ascii=False)

    client = await get_hindsight_client()
    if not client:
        return json.dumps(
            {"success": False, "error": "Memory service not available"},
            ensure_ascii=False,
        )

    try:
        bank_id = _get_bank_id(user_id, bank_name)

        # List memories (with retry for transient failures)
        result = await _run_sync_with_retry(
            client.list_memories,
            bank_id=bank_id,
            type=memory_type,
            limit=limit,
        )

        memories = []
        # result is ListMemoryUnitsResponse with items attribute
        items = result.items if hasattr(result, "items") else result
        for m in items:
            # Each item is a dict with id, text, type, etc.
            if isinstance(m, dict):
                memory_item = {
                    "id": m.get("id", str(hash(str(m)))),
                    "text": m.get("text", str(m)),
                    "type": m.get("type", "unknown"),
                }
            else:
                memory_item = {
                    "id": getattr(m, "id", str(hash(str(m)))),
                    "text": getattr(m, "text", str(m)),
                    "type": getattr(m, "type", "unknown"),
                }
            memories.append(memory_item)

        logger.info(f"[Hindsight] Listed {len(memories)} memories for user {user_id}")

        return json.dumps(
            {
                "success": True,
                "memories": memories,
                "count": len(memories),
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"[Hindsight] Failed to list memories: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
async def memory_delete(
    memory_id: Annotated[str, "The ID of the memory to delete"],
    bank_name: Annotated[Optional[str], "Optional bank name (default: 'default')"] = None,
    runtime: ToolRuntime = None,  # type: ignore[assignment]
) -> str:
    """
    Delete a specific memory by ID.

    Use this tool when a user wants to remove a specific memory.
    Get the memory ID from the memory_list tool output.
    """
    user_id = get_user_id_from_runtime(runtime)
    if not user_id:
        return json.dumps({"success": False, "error": "User not authenticated"}, ensure_ascii=False)

    client = await get_hindsight_client()
    if not client:
        return json.dumps(
            {"success": False, "error": "Memory service not available"},
            ensure_ascii=False,
        )

    try:
        bank_id = _get_bank_id(user_id, bank_name)

        # Check if delete_memory method exists (may not be available in all versions)
        if hasattr(client, "delete_memory"):
            await _run_sync_with_retry(
                client.delete_memory,
                bank_id=bank_id,
                memory_id=memory_id,
            )
            logger.info(f"[Hindsight] Deleted memory {memory_id} for user {user_id}")
        else:
            # Delete operation not supported by current client version
            # The Hindsight client may not expose memory deletion at the individual level
            return json.dumps(
                {
                    "success": False,
                    "error": "Delete operation not supported by the memory service",
                    "hint": "Individual memory deletion may not be available. Consider using bank-level operations.",
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "success": True,
                "message": f"Memory {memory_id} deleted successfully",
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"[Hindsight] Failed to delete memory: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ============================================================================
# Tool Factory Functions
# ============================================================================


def get_memory_retain_tool() -> BaseTool:
    """Get memory_retain tool instance."""
    return memory_retain


def get_memory_recall_tool() -> BaseTool:
    """Get memory_recall tool instance."""
    return memory_recall


def get_memory_reflect_tool() -> BaseTool:
    """Get memory_reflect tool instance."""
    return memory_reflect


def get_memory_list_tool() -> BaseTool:
    """Get memory_list tool instance."""
    return memory_list


def get_memory_delete_tool() -> BaseTool:
    """Get memory_delete tool instance."""
    return memory_delete


def get_all_memory_tools() -> list[BaseTool]:
    """Get all memory tools."""
    return [
        memory_retain,
        memory_recall,
        # memory_reflect,
        # memory_list,
        memory_delete,
    ]


# ============================================================================
# Auto-Retention (Background Task)
# ============================================================================


async def auto_retain_conversation(
    user_id: str,
    conversation_summary: str,
    context: Optional[str] = None,
    bank_name: Optional[str] = None,
) -> None:
    """
    Automatically store conversation summary as memory (fire-and-forget).

    This function is designed to be called at the end of conversations
    to automatically store important information. It runs asynchronously
    and does not block the main response.

    Args:
        user_id: User identifier for multi-tenant isolation
        conversation_summary: Summary of important information from the conversation
        context: Optional context/category for this memory
        bank_name: Optional bank name for organizing memories
    """
    if not user_id or not conversation_summary:
        return

    try:
        client = await get_hindsight_client()
        if not client:
            logger.debug("[Hindsight] Client not available, skipping auto-retain")
            return

        bank_id = _get_bank_id(user_id, bank_name)

        # Ensure bank exists
        await _run_sync_with_retry(_ensure_bank_exists, client, bank_id, bank_name)

        # Retain the memory
        await _run_sync_with_retry(
            client.retain,
            bank_id=bank_id,
            content=conversation_summary,
            context=context or "auto_retained",
        )

        logger.info(
            f"[Hindsight] Auto-retained conversation memory for user {user_id}: "
            f"{conversation_summary}..."
        )

    except Exception as e:
        # Log warning but don't raise - this is a background task
        logger.warning(f"[Hindsight] Auto-retain failed (non-critical): {e}")


def schedule_auto_retain(
    user_id: str,
    conversation_summary: str,
    context: Optional[str] = None,
    bank_name: Optional[str] = None,
) -> None:
    """
    Schedule auto-retention as a background task (fire-and-forget).

    Use this to store conversation memories without blocking the response.
    The task runs in the background and any errors are logged but not raised.

    Args:
        user_id: User identifier for multi-tenant isolation
        conversation_summary: Summary of important information from the conversation
        context: Optional context/category for this memory
        bank_name: Optional bank name for organizing memories
    """
    if not settings.HINDSIGHT_ENABLED:
        return

    if not user_id or not conversation_summary:
        return

    # Try to get the running event loop; if none exists, we can't schedule
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running event loop - this shouldn't happen in our async agents
        logger.debug("[Hindsight] No running event loop, skipping auto-retain")
        return

    # Create background task using the running loop
    task = loop.create_task(
        auto_retain_conversation(
            user_id=user_id,
            conversation_summary=conversation_summary,
            context=context,
            bank_name=bank_name,
        )
    )
    # Add callback to handle any exceptions (prevents "Task exception was never retrieved")
    task.add_done_callback(_handle_background_task_error)


def _handle_background_task_error(task: asyncio.Task) -> None:
    """Handle any exceptions from background tasks."""
    try:
        exc = task.exception()
        if exc:
            logger.warning(f"[Hindsight] Background auto-retain task failed: {exc}")
    except asyncio.CancelledError:
        pass  # Task was cancelled, that's fine


# ============================================================================
# Client Management
# ============================================================================


async def close_hindsight_client() -> None:
    """Close and cleanup the shared Hindsight client and thread pool."""
    global _shared_client
    if _shared_client is not None:
        try:
            if hasattr(_shared_client, "close"):
                _shared_client.close()
            _shared_client = None
            logger.info("[Hindsight] Closed shared client")
        except Exception as e:
            logger.warning(f"[Hindsight] Error closing client: {e}")

    # Shutdown thread pool executor
    _executor.shutdown(wait=False)
    logger.info("[Hindsight] Shutdown thread pool executor")


def get_concurrency_stats() -> dict[str, Any]:
    """
    Get current concurrency statistics.

    Returns:
        Dictionary with concurrency stats for monitoring
    """
    sem_value = _request_semaphore._value if _request_semaphore else _MAX_CONCURRENT_REQUESTS  # type: ignore[attr-defined]
    return {
        "max_workers": _MAX_WORKERS,
        "max_concurrent_requests": _MAX_CONCURRENT_REQUESTS,
        "semaphore_available": sem_value,
        "client_initialized": _shared_client is not None,
    }


# Alias for compatibility
close_all_hindsight_clients = close_hindsight_client
