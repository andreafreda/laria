"""Vendor-neutral memory data types.

These shapes are what the engine sees. Concrete backends (mem0 today, an
in-house L0-L3 engine later) translate to/from their own storage so the engine
never depends on a specific memory product.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Scope:
    """Who a memory belongs to.

    ``household`` is the shared family space; ``user_id`` (optional) marks a
    private per-user space. Access control happens at recall: private items must
    not surface in a shared-scope query.
    """
    household: str = "default"
    user_id: str | None = None

    def key(self) -> str:
        return f"{self.household}/{self.user_id}" if self.user_id else self.household


@dataclass
class MemoryItem:
    """A single recallable unit of memory (an atomic fact/preference/state)."""
    text: str
    scope: Scope = field(default_factory=Scope)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    # Provenance/trust: "user" (said by user) vs "inferred"; 0..1 confidence.
    source: str = "user"
    confidence: float = 1.0
    # Light temporality: epoch seconds.
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Optional relevance score, populated by recall ranking.
    score: float | None = None
