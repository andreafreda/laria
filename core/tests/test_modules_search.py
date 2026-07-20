"""Web search tool tests (no network: the web_search service is stubbed)."""
from __future__ import annotations

import json

from laria.engine import ToolRegistry
from laria.engine.tools import ToolContext
from laria.memory import Scope
from laria.memory.fake import FakeBackend
from laria.modules import register_search_tools
from laria.modules import search as search_module


def _ctx() -> ToolContext:
    return ToolContext(user_id="u1", memory=FakeBackend(), scope=Scope(user_id="u1"))


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_search_tools(registry)
    return registry


def test_tool_registered():
    assert "search_web" in {s["name"] for s in _registry().schemas()}


async def test_search_returns_results(monkeypatch):
    async def fake_search(query, count):
        return [{"title": "San Marco", "url": "u", "snippet": "25 aprile"}]

    monkeypatch.setattr(search_module.web_search, "search", fake_search)
    out = await _registry().dispatch("search_web", {"query": "onomastico Marco"}, _ctx())
    assert "25 aprile" in out


async def test_empty_query_is_rejected():
    out = await _registry().dispatch("search_web", {"query": "  "}, _ctx())
    assert "Provide a search query" in out


async def test_no_results(monkeypatch):
    async def empty(query, count):
        return []

    monkeypatch.setattr(search_module.web_search, "search", empty)
    out = await _registry().dispatch("search_web", {"query": "zzz"}, _ctx())
    assert "No web results" in out
