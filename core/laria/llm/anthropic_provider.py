"""Anthropic implementation of ``LLMProvider`` (phase 1 default).

Maps the normalized request/response types to the Anthropic Messages API.
Honors ``cache_control`` hints already present on system/tool blocks (the
extended 1h TTL beta header is sent so callers can opt into long caching).
"""
from __future__ import annotations

from typing import Any

import anthropic

from .base import LLMProvider, LLMResponse, TextBlock, ToolUseBlock


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, default_model: str):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the anthropic provider")
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._default_model = default_model

    def supports_prompt_cache(self) -> bool:
        return True

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
        kwargs: dict[str, Any] = {
            "model": model or self._default_model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            # Opt into extended (1h) prompt-cache TTL when callers set it.
            "extra_headers": {"anthropic-beta": "extended-cache-ttl-2025-04-11"},
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        resp = await self._client.messages.create(**kwargs)

        blocks: list[TextBlock | ToolUseBlock] = []
        for block in resp.content:
            if block.type == "text":
                blocks.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                blocks.append(ToolUseBlock(id=block.id, name=block.name, input=block.input))
        return LLMResponse(blocks=blocks, stop_reason=resp.stop_reason, raw=resp)
