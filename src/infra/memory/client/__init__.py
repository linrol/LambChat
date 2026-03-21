"""
Memory backend clients.

Each client implements the MemoryBackend interface from base.py.
Use create_memory_backend() factory to get the active backend.
"""

from src.infra.memory.client.base import (
    MemoryBackend,
    create_memory_backend,
    is_memory_enabled,
)
from src.infra.memory.client.hindsight import HindsightBackend
from src.infra.memory.client.memu import MemuBackend

__all__ = [
    "MemoryBackend",
    "HindsightBackend",
    "MemuBackend",
    "create_memory_backend",
    "is_memory_enabled",
]
