"""Memory backend selection from settings.

The only place that knows which concrete backend is active. Engine code calls
``get_memory_backend()`` and depends solely on the MemoryBackend interface.
"""
from __future__ import annotations

from ..config import Settings, get_settings
from .base import MemoryBackend


def get_memory_backend(settings: Settings | None = None) -> MemoryBackend:
    s = settings or get_settings()
    backend = s.memory.backend.lower()

    if backend == "fake":
        from .fake import FakeBackend
        return FakeBackend()

    if backend == "mem0":
        from .mem0_backend import Mem0Backend
        return Mem0Backend()

    raise ValueError(
        f"Unsupported memory backend: {backend!r}. "
        "Supported now: 'fake', 'mem0'. (in-house L0-L3 engine later.)"
    )
