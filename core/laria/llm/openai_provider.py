"""OpenAI-compatible provider (OpenAI, Ollama, LM Studio, vLLM, and friends).

These backends all speak the OpenAI Chat Completions API, so one provider covers
them; only the base URL and key change. The engine speaks a vendor-neutral,
Anthropic-shaped message format, so the work here is translating that to and from
the OpenAI shape. The translation is kept in small pure functions (easy to read
and test); the class only adds the HTTP call.
"""
from __future__ import annotations

import json
from typing import Any

import aiohttp

from .base import LLMProvider, LLMResponse, TextBlock, ToolUseBlock

_TIMEOUT = aiohttp.ClientTimeout(total=120)


def _system_text(system: str | list[dict[str, Any]]) -> str:
    """Flatten our system prompt (a string or text blocks) into one string.

    Anthropic-style cache_control hints on the blocks are dropped, since the
    OpenAI API has no equivalent.
    """
    if isinstance(system, str):
        return system
    return "\n\n".join(block.get("text", "") for block in system)


def to_openai_messages(system: str | list[dict[str, Any]],
                       messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert the neutral system prompt and messages to OpenAI chat messages.

    Mappings: a tool_use block becomes an assistant ``tool_calls`` entry; a
    tool_result block becomes a separate ``role: tool`` message keyed by the
    tool_call id; plain text content passes through unchanged.
    """
    out: list[dict[str, Any]] = [{"role": "system", "content": _system_text(system)}]
    for message in messages:
        role, content = message["role"], message["content"]
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        out.extend(_convert_block_message(role, content))
    return out


def _convert_block_message(role: str, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert one neutral block-list message into one or more OpenAI messages."""
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    for block in blocks:
        kind = block.get("type")
        if kind == "text":
            text_parts.append(block.get("text", ""))
        elif kind == "tool_use":
            tool_calls.append({
                "id": block["id"],
                "type": "function",
                "function": {"name": block["name"],
                             "arguments": json.dumps(block.get("input", {}))},
            })
        elif kind == "tool_result":
            tool_results.append({
                "role": "tool",
                "tool_call_id": block["tool_use_id"],
                "content": block.get("content", ""),
            })

    out: list[dict[str, Any]] = []
    if text_parts or tool_calls:
        assistant: dict[str, Any] = {"role": role,
                                     "content": "\n".join(text_parts) or None}
        if tool_calls:
            assistant["tool_calls"] = tool_calls
        out.append(assistant)
    out.extend(tool_results)
    return out


def to_openai_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    """Convert neutral tool schemas to OpenAI function-tool schemas."""
    if not tools:
        return None
    return [
        {"type": "function",
         "function": {"name": t["name"], "description": t.get("description", ""),
                      "parameters": t.get("input_schema", {})}}
        for t in tools
    ]


def to_openai_tool_choice(tool_choice: dict[str, Any] | None) -> Any:
    """Map our tool_choice to OpenAI's: any becomes required, a named tool stays
    named, anything else is left to the model (auto)."""
    if not tool_choice:
        return None
    if tool_choice.get("type") == "any":
        return "required"
    if tool_choice.get("type") == "tool":
        return {"type": "function", "function": {"name": tool_choice["name"]}}
    return "auto"


def parse_response(data: dict[str, Any]) -> LLMResponse:
    """Turn an OpenAI chat-completion response into our normalized LLMResponse.

    Tool-call arguments arrive as a JSON string and are parsed back into a dict;
    a malformed one yields an empty input rather than crashing the turn.
    """
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message", {})
    blocks: list[TextBlock | ToolUseBlock] = []
    if message.get("content"):
        blocks.append(TextBlock(text=message["content"]))
    for call in message.get("tool_calls") or []:
        function = call.get("function", {})
        blocks.append(ToolUseBlock(
            id=call.get("id", ""),
            name=function.get("name", ""),
            input=_parse_arguments(function.get("arguments")),
        ))
    return LLMResponse(blocks=blocks, stop_reason=choice.get("finish_reason"), raw=data)


def _parse_arguments(arguments: str | None) -> dict[str, Any]:
    try:
        return json.loads(arguments) if arguments else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class OpenAICompatibleProvider(LLMProvider):
    name = "openai"

    def __init__(self, base_url: str, api_key: str, default_model: str):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._default_model = default_model

    def supports_prompt_cache(self) -> bool:
        return False

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
        payload: dict[str, Any] = {
            "model": model or self._default_model,
            "max_tokens": max_tokens,
            "messages": to_openai_messages(system, messages),
        }
        openai_tools = to_openai_tools(tools)
        if openai_tools:
            payload["tools"] = openai_tools
            choice = to_openai_tool_choice(tool_choice)
            if choice is not None:
                payload["tool_choice"] = choice

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.post(f"{self._base_url}/chat/completions",
                                    headers=headers, json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json()
        return parse_response(data)
