import pytest

import laria.config as config
from laria.llm import LLMResponse, TextBlock, ToolUseBlock, get_provider


def test_response_helpers():
    r = LLMResponse(blocks=[
        TextBlock(text="hello "),
        ToolUseBlock(id="t1", name="do_thing", input={"x": 1}),
        TextBlock(text="world"),
    ])
    assert r.text == "hello world"
    assert len(r.tool_uses) == 1
    assert r.tool_uses[0].name == "do_thing"


def test_registry_unsupported(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(ValueError):
        get_provider(config.reload_settings())


def test_registry_anthropic_requires_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError):
        get_provider(config.reload_settings())
