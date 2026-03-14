"""
Memory Infrastructure Module

Provides cross-session long-term memory capabilities through Hindsight integration.
Uses shared Hindsight server with bank_id isolation for multi-tenancy.
"""

from src.infra.memory.hindsight import (
    close_all_hindsight_clients,
    close_hindsight_client,
    get_all_memory_tools,
    get_hindsight_client,
    get_memory_delete_tool,
    get_memory_list_tool,
    get_memory_recall_tool,
    get_memory_reflect_tool,
    get_memory_retain_tool,
)

__all__ = [
    "get_hindsight_client",
    "get_all_memory_tools",
    "get_memory_retain_tool",
    "get_memory_recall_tool",
    "get_memory_reflect_tool",
    "get_memory_list_tool",
    "get_memory_delete_tool",
    "close_hindsight_client",
    "close_all_hindsight_clients",
]
