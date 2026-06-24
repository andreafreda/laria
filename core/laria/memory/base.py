"""MemoryBackend — the public memory API the engine depends on.

This is the seam that makes the memory engine plug & play: the agent calls only
these methods. Phase 1 the concrete backend is mem0 (see ``mem0_backend``); a
future in-house L0-L3 store drops in here without touching the engine.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .types import MemoryItem, Scope


class MemoryBackend(ABC):
    """Vendor-neutral agent memory."""

    name: str = "base"

    @abstractmethod
    def write(self, scope: Scope, text: str, *, source: str = "user",
              confidence: float = 1.0, metadata: dict | None = None) -> MemoryItem:
        """Ingest raw text and persist the extracted memory.

        Extraction (what becomes a durable fact) is the backend's concern; the
        engine just hands over what was said/observed.
        """
        raise NotImplementedError

    @abstractmethod
    def recall(self, scope: Scope, query: str, *, k: int = 5,
               filters: dict | None = None) -> list[MemoryItem]:
        """Return the ``k`` most relevant items for ``query`` within ``scope``.

        Hybrid (vector + keyword) + re-rank is the goal; private items outside
        ``scope`` must never surface.
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, scope: Scope, item_id: str) -> MemoryItem | None:
        raise NotImplementedError

    @abstractmethod
    def update(self, scope: Scope, item_id: str, *, text: str | None = None,
               metadata: dict | None = None) -> MemoryItem | None:
        """Edit an item in place (deterministic CRUD, not agent self-rewrite)."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, scope: Scope, item_id: str) -> bool:
        """Hard-delete one item. Returns True if it existed."""
        raise NotImplementedError

    @abstractmethod
    def forget(self, scope: Scope, *, selector: dict | None = None) -> int:
        """Bulk forget within scope (decay/TTL/clear). Returns count removed."""
        raise NotImplementedError
