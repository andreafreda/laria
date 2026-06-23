"""Provider-agnostic LLM layer.

The engine talks to ``LLMProvider`` only; concrete providers (Anthropic now,
OpenAI/Ollama later) adapt their SDK to the normalized request/response types
defined in ``laria.llm.base``.
"""
from .base import (
    LLMProvider,
    LLMResponse,
    TextBlock,
    ToolUseBlock,
    ToolResult,
)
from .registry import get_provider

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "TextBlock",
    "ToolUseBlock",
    "ToolResult",
    "get_provider",
]
