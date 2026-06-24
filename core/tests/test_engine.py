"""Engine loop tests with a scripted fake provider (no network)."""
from __future__ import annotations

import os

import pytest

from laria.config import reload_settings
from laria.engine import Engine, Tool, ToolRegistry
from laria.llm.base import LLMProvider, LLMResponse, TextBlock, ToolUseBlock
from laria.memory.fake import FakeBackend
from laria.storage import conversations as conv
from laria.storage import init_db


class FakeProvider(LLMProvider):
    """Returns queued LLMResponses in order; records requests."""
    name = "fake"

    def __init__(self, scripted: list[LLMResponse]):
        self._scripted = list(scripted)
        self.calls: list[dict] = []

    def supports_prompt_cache(self) -> bool:
        return False

    async def generate(self, *, system, messages, tools=None, tool_choice=None,
                       max_tokens=4096, model=None) -> LLMResponse:
        self.calls.append({"messages": messages, "tool_choice": tool_choice})
        return self._scripted.pop(0)


def _respond(text: str, _id="r1") -> LLMResponse:
    return LLMResponse(blocks=[ToolUseBlock(id=_id, name="respond", input={"text": text})],
                       stop_reason="tool_use")


def _tool_use(name: str, inp: dict, _id="t1") -> LLMResponse:
    return LLMResponse(blocks=[ToolUseBlock(id=_id, name=name, input=inp)],
                       stop_reason="tool_use")


@pytest.fixture
async def db(tmp_path):
    os.environ["LARIA_DB_PATH"] = str(tmp_path / "test.db")
    os.environ["LARIA_DATA_DIR"] = str(tmp_path)
    reload_settings()
    await init_db()
    yield
    os.environ.pop("LARIA_DB_PATH", None)
    os.environ.pop("LARIA_DATA_DIR", None)
    reload_settings()


async def test_simple_respond(db):
    provider = FakeProvider([_respond("hello there")])
    eng = Engine(provider, FakeBackend())
    out = await eng.chat("u1", "hi")
    assert out == "hello there"
    hist = await conv.get_history("u1")
    assert hist[0]["content"] == "hi"
    assert hist[1]["content"] == "hello there"


async def test_tool_then_respond(db):
    calls = []

    async def handler(inputs, ctx):
        calls.append(inputs)
        return "tool-output"

    reg = ToolRegistry()
    reg.register(Tool("ping", "ping", {"type": "object", "properties": {}}, handler))

    provider = FakeProvider([_tool_use("ping", {}), _respond("done")])
    eng = Engine(provider, FakeBackend(), registry=reg)
    out = await eng.chat("u1", "do it")
    assert out == "done"
    assert calls == [{}]
    # second call must carry the tool_result back
    assert any(m["role"] == "user" and isinstance(m["content"], list)
               for m in provider.calls[1]["messages"])


async def test_save_and_recall_memory(db):
    mem = FakeBackend()
    # turn 1: save_memory; turn 2: respond
    provider = FakeProvider([
        _tool_use("save_memory", {"key": "wifi", "value": "pass123"}),
        _respond("saved"),
    ])
    eng = Engine(provider, mem)
    out = await eng.chat("u1", "remember my wifi pass123")
    assert out == "saved"
    assert (await conv.get_notes("u1"))["wifi"] == "pass123"
    # indexed in semantic memory too
    from laria.memory import Scope
    assert mem.recall(Scope(user_id="u1"), "wifi")


async def test_deferred_respond(db):
    """respond emitted together with a tool is deferred one turn."""
    async def handler(inputs, ctx):
        return "ok"

    reg = ToolRegistry()
    reg.register(Tool("act", "act", {"type": "object", "properties": {}}, handler))

    both = LLMResponse(blocks=[
        ToolUseBlock(id="a1", name="act", input={}),
        ToolUseBlock(id="r1", name="respond", input={"text": "early"}),
    ], stop_reason="tool_use")
    provider = FakeProvider([both, _respond("final")])
    eng = Engine(provider, FakeBackend(), registry=reg)
    out = await eng.chat("u1", "go")
    assert out == "final"  # early reply was deferred


async def test_max_turns_force_respond(db):
    # always returns a tool_use; final turn forces respond via tool_choice
    async def handler(inputs, ctx):
        return "loop"

    reg = ToolRegistry()
    reg.register(Tool("act", "act", {"type": "object", "properties": {}}, handler))

    scripted = [_tool_use("act", {}, _id=f"t{i}") for i in range(7)] + [_respond("stopped")]
    provider = FakeProvider(scripted)
    eng = Engine(provider, FakeBackend(), registry=reg, max_turns=8)
    out = await eng.chat("u1", "spin")
    assert out == "stopped"
    assert provider.calls[-1]["tool_choice"] == {"type": "tool", "name": "respond"}
