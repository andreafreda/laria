"""mem0 wrapper — phase-1 concrete backend behind MemoryBackend.

mem0 (Apache-2.0, local-capable) does fact extraction with ADD/UPDATE/DELETE/
NOOP. We keep it strictly behind this wrapper so the engine never imports mem0
directly: swapping to an in-house engine later is a one-line registry change.

Scope maps to mem0's ``user_id`` namespace via ``Scope.key()``.
``mem0`` is an optional dependency; the import is lazy so the package installs
and tests run without it (use FakeBackend).
"""
from __future__ import annotations

import time
from typing import Any

from .base import MemoryBackend
from .types import MemoryItem, Scope


class Mem0Backend(MemoryBackend):
    name = "mem0"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        try:
            from mem0 import Memory  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise RuntimeError(
                "mem0 backend selected but 'mem0ai' is not installed. "
                "Install it or set MEMORY_BACKEND=fake."
            ) from exc
        self._mem = Memory.from_config(config) if config else Memory()

    def _to_item(self, raw: dict[str, Any], scope: Scope) -> MemoryItem:
        return MemoryItem(
            id=str(raw.get("id", "")),
            text=raw.get("memory") or raw.get("text") or "",
            scope=scope,
            metadata=raw.get("metadata") or {},
            score=raw.get("score"),
        )

    def write(self, scope: Scope, text: str, *, source: str = "user",
              confidence: float = 1.0, metadata: dict | None = None) -> MemoryItem:
        meta = {"source": source, "confidence": confidence, **(metadata or {})}
        res = self._mem.add(text, user_id=scope.key(), metadata=meta)
        # mem0 returns the extraction result; surface a best-effort item.
        results = res.get("results") if isinstance(res, dict) else None
        if results:
            return self._to_item(results[0], scope)
        item = MemoryItem(text=text, scope=scope, source=source,
                          confidence=confidence, metadata=metadata or {})
        return item

    def recall(self, scope: Scope, query: str, *, k: int = 5,
               filters: dict | None = None) -> list[MemoryItem]:
        res = self._mem.search(query, user_id=scope.key(), limit=k)
        results = res.get("results", res) if isinstance(res, dict) else res
        return [self._to_item(r, scope) for r in (results or [])]

    def get(self, scope: Scope, item_id: str) -> MemoryItem | None:
        raw = self._mem.get(item_id)
        return self._to_item(raw, scope) if raw else None

    def update(self, scope: Scope, item_id: str, *, text: str | None = None,
               metadata: dict | None = None) -> MemoryItem | None:
        if text is not None:
            self._mem.update(memory_id=item_id, data=text)
        raw = self._mem.get(item_id)
        if not raw:
            return None
        item = self._to_item(raw, scope)
        if metadata is not None:
            item.metadata.update(metadata)
        item.updated_at = time.time()
        return item

    def delete(self, scope: Scope, item_id: str) -> bool:
        self._mem.delete(memory_id=item_id)
        return True

    def forget(self, scope: Scope, *, selector: dict | None = None) -> int:
        self._mem.delete_all(user_id=scope.key())
        return -1  # mem0 doesn't report a count
