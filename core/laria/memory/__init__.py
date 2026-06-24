"""Agent memory — vendor-neutral interface + swappable backends.

Engine imports from here only:
    from laria.memory import MemoryBackend, MemoryItem, Scope, get_memory_backend
"""
from __future__ import annotations

from .base import MemoryBackend
from .embedder import Embedder
from .registry import get_memory_backend
from .types import MemoryItem, Scope

__all__ = [
    "MemoryBackend",
    "Embedder",
    "MemoryItem",
    "Scope",
    "get_memory_backend",
]
