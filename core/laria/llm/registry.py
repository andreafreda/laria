"""Provider selection from settings."""
from __future__ import annotations

from ..config import Settings, get_settings
from .base import LLMProvider


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Instantiate the configured LLM provider.

    Phase 1 supports Anthropic. OpenAI-compatible (Ollama/LM Studio/vLLM) and
    others plug in here without touching the engine.
    """
    s = settings or get_settings()
    provider = s.llm.provider.lower()

    if provider == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=s.llm.anthropic_api_key, default_model=s.llm.model)

    raise ValueError(
        f"Unsupported LLM provider: {provider!r}. "
        "Supported now: 'anthropic'. (openai/ollama coming.)"
    )
