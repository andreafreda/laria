"""In-memory backend: no network, no deps. Default for tests and dev.

Recall is naive substring/keyword overlap — enough to exercise the engine and
the MemoryBackend contract without pulling in mem0 or an embedding model.
"""
from __future__ import annotations

import time

from .base import MemoryBackend
from .types import MemoryItem, Scope


def _visible(item_scope: Scope, query_scope: Scope) -> bool:
    """A query in ``query_scope`` sees shared household items plus its own
    private items, never another user's private items."""
    if item_scope.household != query_scope.household:
        return False
    if item_scope.user_id is None:
        return True  # shared household item
    return item_scope.user_id == query_scope.user_id


class FakeBackend(MemoryBackend):
    """Dict-backed memory. Not persistent."""

    name = "fake"

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}

    def write(self, scope: Scope, text: str, *, source: str = "user",
              confidence: float = 1.0, metadata: dict | None = None) -> MemoryItem:
        item = MemoryItem(text=text, scope=scope, source=source,
                          confidence=confidence, metadata=metadata or {})
        self._items[item.id] = item
        return item

    def recall(self, scope: Scope, query: str, *, k: int = 5,
               filters: dict | None = None) -> list[MemoryItem]:
        terms = {t for t in query.lower().split() if t}
        scored: list[MemoryItem] = []
        for item in self._items.values():
            if not _visible(item.scope, scope):
                continue
            words = set(item.text.lower().split())
            overlap = len(terms & words)
            if overlap or not terms:
                item.score = float(overlap)
                scored.append(item)
        scored.sort(key=lambda i: (i.score or 0.0, i.updated_at), reverse=True)
        return scored[:k]

    def get(self, scope: Scope, item_id: str) -> MemoryItem | None:
        item = self._items.get(item_id)
        if item and _visible(item.scope, scope):
            return item
        return None

    def update(self, scope: Scope, item_id: str, *, text: str | None = None,
               metadata: dict | None = None) -> MemoryItem | None:
        item = self.get(scope, item_id)
        if item is None:
            return None
        if text is not None:
            item.text = text
        if metadata is not None:
            item.metadata.update(metadata)
        item.updated_at = time.time()
        return item

    def delete(self, scope: Scope, item_id: str) -> bool:
        item = self.get(scope, item_id)
        if item is None:
            return False
        del self._items[item_id]
        return True

    def forget(self, scope: Scope, *, selector: dict | None = None) -> int:
        to_remove = [i.id for i in self._items.values() if _visible(i.scope, scope)]
        for iid in to_remove:
            del self._items[iid]
        return len(to_remove)
