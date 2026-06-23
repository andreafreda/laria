"""Normalized, provider-agnostic LLM types and interface.

Goal: the agentic engine builds a request once (system prompt, tool schemas,
conversation messages) and gets back a uniform response (text + tool calls),
regardless of which vendor is behind it. Providers translate to/from their own
SDK shapes.

Message format (vendor-neutral, Anthropic-like since it maps cleanly):
    {"role": "user"|"assistant", "content": <str | list[block]>}
where a block is one of:
    {"type": "text", "text": str}
    {"type": "tool_use", "id": str, "name": str, "input": dict}
    {"type": "tool_result", "tool_use_id": str, "content": str}
Providers that don't speak this natively (e.g. OpenAI/Ollama) convert internally.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextBlock:
    text: str


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResult:
    """A tool's output to feed back into the conversation."""
    tool_use_id: str
    content: str

    def to_message_block(self) -> dict[str, Any]:
        return {"type": "tool_result", "tool_use_id": self.tool_use_id, "content": self.content}


@dataclass
class LLMResponse:
    """Normalized model output for one turn."""
    blocks: list[TextBlock | ToolUseBlock] = field(default_factory=list)
    stop_reason: str | None = None
    raw: Any = None  # original SDK object, for debugging

    @property
    def text(self) -> str:
        return "".join(b.text for b in self.blocks if isinstance(b, TextBlock))

    @property
    def tool_uses(self) -> list[ToolUseBlock]:
        return [b for b in self.blocks if isinstance(b, ToolUseBlock)]


class LLMProvider(ABC):
    """Interface every LLM backend implements."""

    name: str = "base"

    @abstractmethod
    async def generate(
        self,
        *,
        system: str | list[dict[str, Any]],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> LLMResponse:
        """Run one model turn and return a normalized response.

        ``tools`` use the vendor-neutral JSON-schema shape
        ``{"name", "description", "input_schema"}``; providers remap as needed.
        """
        raise NotImplementedError

    def supports_prompt_cache(self) -> bool:
        """Whether ``cache_control`` hints are honored (Anthropic: yes)."""
        return False
