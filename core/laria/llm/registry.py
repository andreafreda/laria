"""Provider selection from settings."""
from __future__ import annotations

from ..config import Settings, get_settings
from .base import LLMProvider


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Instantiate the configured LLM provider.

    Supports Anthropic and any OpenAI-compatible endpoint: 'openai' for OpenAI
    itself, 'ollama' for a local Ollama server, and the generic
    'openai-compatible' for LM Studio, vLLM and similar. New providers plug in
    here without touching the engine.
    """
    s = settings or get_settings()
    provider = s.llm.provider.lower()

    if provider == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=s.llm.anthropic_api_key, default_model=s.llm.model)

    if provider in ("openai", "openai-compatible"):
        from .openai_provider import OpenAICompatibleProvider
        return OpenAICompatibleProvider(
            base_url=s.llm.openai_base_url,
            api_key=s.llm.openai_api_key,
            default_model=s.llm.model,
        )

    if provider == "ollama":
        from .openai_provider import OpenAICompatibleProvider
        # Ollama serves the OpenAI API under /v1 and ignores the key.
        return OpenAICompatibleProvider(
            base_url=f"{s.llm.ollama_base_url.rstrip('/')}/v1",
            api_key="",
            default_model=s.llm.model,
        )

    raise ValueError(
        f"Unsupported LLM provider: {provider!r}. "
        "Supported: 'anthropic', 'openai', 'openai-compatible', 'ollama'."
    )
