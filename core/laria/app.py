"""Composition root: wire the pieces into a ready-to-use engine.

This is the one place that knows how the parts fit together (LLM provider plus
memory backend plus the domain tool modules). Everything else depends on
abstractions, so swapping a provider or a backend happens here, not in the
engine. Channels (web API, Telegram, ...) call ``build_engine`` and then talk to
the engine.
"""
from __future__ import annotations

from .config import Settings, get_settings
from .engine import Engine, ToolRegistry
from .llm import get_provider
from .memory import get_memory_backend
from .modules import (
    register_finance_tools,
    register_food_tools,
    register_utilities_tools,
)


def build_engine(settings: Settings | None = None) -> Engine:
    """Assemble the agent engine from configuration.

    Reads the active LLM provider and memory backend from settings, registers
    every domain's tools, and returns an Engine ready to ``chat``. Raises if the
    configured provider is missing its credentials, so misconfiguration fails at
    startup rather than on the first request.
    """
    settings = settings or get_settings()
    provider = get_provider(settings)
    memory = get_memory_backend(settings)

    registry = ToolRegistry()
    register_finance_tools(registry)
    register_food_tools(registry)
    register_utilities_tools(registry)

    return Engine(provider, memory, registry=registry, settings=settings)
