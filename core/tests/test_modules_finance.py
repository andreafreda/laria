"""Finance module tests: tools wired to storage, driven through the engine."""
from __future__ import annotations

import json
import os

import pytest

from laria.config import reload_settings
from laria.engine import Engine, ToolRegistry
from laria.engine.tools import ToolContext
from laria.llm.base import LLMProvider, LLMResponse, ToolUseBlock
from laria.memory import Scope
from laria.memory.fake import FakeBackend
from laria.modules import register_finance_tools
from laria.storage import finance, init_db


class FakeProvider(LLMProvider):
    """Returns queued responses in order (no network)."""
    name = "fake"

    def __init__(self, scripted: list[LLMResponse]):
        self._scripted = list(scripted)

    def supports_prompt_cache(self) -> bool:
        return False

    async def generate(self, *, system, messages, tools=None, tool_choice=None,
                       max_tokens=4096, model=None) -> LLMResponse:
        return self._scripted.pop(0)


def _tool_use(name, inputs, _id="t1"):
    return LLMResponse(blocks=[ToolUseBlock(id=_id, name=name, input=inputs)],
                       stop_reason="tool_use")


def _respond(text, _id="r1"):
    return LLMResponse(blocks=[ToolUseBlock(id=_id, name="respond", input={"text": text})],
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


def _registry_with_finance() -> ToolRegistry:
    registry = ToolRegistry()
    register_finance_tools(registry)
    return registry


async def test_finance_tools_are_registered(db):
    names = {schema["name"] for schema in _registry_with_finance().schemas()}
    assert "add_transaction" in names
    assert "get_balances" in names
    assert "expense_summary" in names


async def test_add_transaction_through_engine(db):
    await finance.add_account("checking", "bank", opening_balance=100.0)
    provider = FakeProvider([
        _tool_use("add_transaction",
                  {"account": "checking", "amount": -30.0, "category": "groceries",
                   "date": "2026-02-01"}),
        _respond("Recorded it."),
    ])
    engine = Engine(provider, FakeBackend(), registry=_registry_with_finance())

    reply = await engine.chat("u1", "I spent 30 on groceries")

    assert reply == "Recorded it."
    assert await finance.get_balance("checking") == 70.0


async def test_get_balances_dispatch(db):
    await finance.add_account("checking", "bank", opening_balance=250.0)
    registry = _registry_with_finance()
    ctx = ToolContext(user_id="u1", memory=FakeBackend(), scope=Scope(user_id="u1"))

    result = await registry.dispatch("get_balances", {}, ctx)

    balances = json.loads(result)
    assert balances[0]["account"] == "checking"
    assert balances[0]["balance"] == 250.0
