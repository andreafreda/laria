"""Abstract embedder.

The memory engine never hard-codes an embedding model. Default deployment uses
a local embedder (sentence-transformers / Ollama); cloud (Voyage/OpenAI) is
opt-in. Tests use a deterministic fake (see tests) so they need no network.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Embedder(ABC):
    """Turns text into vectors. One implementation per model/provider."""

    name: str = "base"
    dim: int = 0

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text (same order)."""
        raise NotImplementedError

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
