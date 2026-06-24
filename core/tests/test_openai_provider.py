"""OpenAI-compatible provider: format conversion and registry wiring (no network)."""
from __future__ import annotations

import os

from laria.config import reload_settings
from laria.llm import get_provider
from laria.llm.openai_provider import (
    OpenAICompatibleProvider,
    parse_response,
    to_openai_messages,
    to_openai_tool_choice,
    to_openai_tools,
)


def test_messages_flatten_system_and_blocks():
    system = [{"type": "text", "text": "You are helpful."}]
    messages = [
        {"role": "user", "content": "turn on the light"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "c1", "name": "control", "input": {"on": True}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "c1", "content": "done"},
        ]},
    ]
    result = to_openai_messages(system, messages)

    assert result[0] == {"role": "system", "content": "You are helpful."}
    assert result[1] == {"role": "user", "content": "turn on the light"}
    assistant = result[2]
    assert assistant["tool_calls"][0]["function"]["name"] == "control"
    assert assistant["tool_calls"][0]["function"]["arguments"] == '{"on": true}'
    assert result[3] == {"role": "tool", "tool_call_id": "c1", "content": "done"}


def test_tools_and_tool_choice_mapping():
    tools = [{"name": "f", "description": "d", "input_schema": {"type": "object"}}]
    converted = to_openai_tools(tools)
    assert converted[0]["type"] == "function"
    assert converted[0]["function"]["parameters"] == {"type": "object"}

    assert to_openai_tool_choice({"type": "any"}) == "required"
    assert to_openai_tool_choice({"type": "tool", "name": "respond"}) == {
        "type": "function", "function": {"name": "respond"}}
    assert to_openai_tool_choice(None) is None


def test_parse_response_text_and_tool_calls():
    data = {"choices": [{"finish_reason": "tool_calls", "message": {
        "content": "ok",
        "tool_calls": [
            {"id": "c1", "function": {"name": "f", "arguments": '{"x": 1}'}},
            {"id": "c2", "function": {"name": "g", "arguments": "not json"}},
        ],
    }}]}
    response = parse_response(data)

    assert response.text == "ok"
    tool_uses = response.tool_uses
    assert tool_uses[0].name == "f" and tool_uses[0].input == {"x": 1}
    assert tool_uses[1].input == {}  # malformed arguments degrade to empty


def test_registry_selects_ollama_with_v1_base():
    os.environ["LLM_PROVIDER"] = "ollama"
    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
    reload_settings()
    try:
        provider = get_provider()
        assert isinstance(provider, OpenAICompatibleProvider)
        assert provider._base_url == "http://localhost:11434/v1"
    finally:
        os.environ.pop("LLM_PROVIDER", None)
        os.environ.pop("OLLAMA_BASE_URL", None)
        reload_settings()


def test_registry_selects_openai():
    os.environ["LLM_PROVIDER"] = "openai"
    os.environ["OPENAI_API_KEY"] = "sk-test"
    reload_settings()
    try:
        provider = get_provider()
        assert isinstance(provider, OpenAICompatibleProvider)
        assert provider._base_url == "https://api.openai.com/v1"
    finally:
        os.environ.pop("LLM_PROVIDER", None)
        os.environ.pop("OPENAI_API_KEY", None)
        reload_settings()
