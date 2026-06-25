"""News module tests: topic parsing, query building, and briefing generation."""
from __future__ import annotations

import json
import os

import pytest

from laria.config import reload_settings
from laria.engine import ToolRegistry
from laria.engine.tools import ToolContext
from laria.llm import LLMResponse, TextBlock
from laria.memory import Scope
from laria.memory.fake import FakeBackend
from laria.modules import news
from laria.modules.news import _build_query, _dump_topics, _parse_topics, register_news_tools
from laria.storage import init_db


class FakeProvider:
    """Returns a fixed summary so briefing generation is deterministic."""

    def __init__(self, text: str = "summary"):
        self.text = text

    async def generate(self, **_kwargs) -> LLMResponse:
        return LLMResponse(blocks=[TextBlock(text=self.text)])


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


def test_parse_topics_reads_json_and_legacy_csv():
    parsed = _parse_topics('[{"topic": "ai", "sources": ["wired.com"]}]')
    assert parsed == [{"topic": "ai", "sources": ["wired.com"]}]
    legacy = _parse_topics("ai, markets")
    assert legacy == [{"topic": "ai", "sources": []}, {"topic": "markets", "sources": []}]


def test_dump_topics_normalizes():
    dumped = _dump_topics([{"topic": " AI ", "sources": [" Wired.com "]}, "markets"])
    assert json.loads(dumped) == [
        {"topic": "AI", "sources": ["wired.com"]},
        {"topic": "markets", "sources": []},
    ]


def test_build_query_applies_sources_and_blocks():
    query = _build_query("ai", ["wired.com"], ["spam.example"])
    assert "site:wired.com" in query
    assert "-site:spam.example" in query


async def test_generate_summarizes_results(monkeypatch):
    async def fake_news(_query, _max):
        return [{"title": "T", "snippet": "S", "url": "u", "date": "today", "source": "src"}]

    monkeypatch.setattr(news.web_search, "search_news", fake_news)
    result = await news.generate(FakeProvider("the summary"),
                                 '[{"topic": "ai"}]', user_id="", num_news=3)
    assert result == "the summary"


async def test_generate_handles_no_results(monkeypatch):
    async def empty(_query, _max):
        return []

    monkeypatch.setattr(news.web_search, "search_news", empty)
    monkeypatch.setattr(news.web_search, "search", empty)
    result = await news.generate(FakeProvider(), '[{"topic": "ai"}]', num_news=3)
    assert "No news found" in result


async def test_create_and_list_briefing(db):
    registry = ToolRegistry()
    register_news_tools(registry, FakeProvider(), scheduler=None)
    ctx = ToolContext(user_id="7", memory=FakeBackend(), scope=Scope(user_id="7"))

    created = json.loads(await registry.dispatch(
        "create_briefing", {"topics": [{"topic": "ai"}], "cron": "0 8 * * *"}, ctx))
    assert created["ok"] is True

    listed = json.loads(await registry.dispatch("list_briefings", {}, ctx))
    assert listed[0]["topics"] == [{"topic": "ai", "sources": []}]
