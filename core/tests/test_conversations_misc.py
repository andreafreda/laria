"""Conversation-store + misc storage tests on a temp DB (no network)."""
from __future__ import annotations

import os

import pytest

from laria.config import reload_settings
from laria.storage import conversations as conv
from laria.storage import init_db, misc


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


async def test_history_roundtrip(db):
    await conv.save_turn("u1", "user", "hello")
    await conv.save_turn("u1", "assistant", "hi")
    hist = await conv.get_history("u1")
    assert [h["role"] for h in hist] == ["user", "assistant"]
    assert await conv.count_history("u1") == 2
    await conv.clear_history("u1")
    assert await conv.count_history("u1") == 0


async def test_summary_and_old_turns(db):
    for i in range(15):
        await conv.save_turn("u1", "user", f"msg{i}")
    old = await conv.get_old_turns("u1", keep=10, batch=20)
    assert len(old) == 5  # 15 - 10 kept
    await conv.delete_turns([o["id"] for o in old])
    assert await conv.count_history("u1") == 10

    await conv.set_summary("u1", "a summary")
    assert await conv.get_summary("u1") == "a summary"


async def test_notes(db):
    await conv.save_note("u1", "favorite_color", "blue")
    await conv.save_note("u1", "favorite_color", "green")  # upsert
    notes = await conv.get_notes("u1")
    assert notes["favorite_color"] == "green"


async def test_reminders(db):
    r = await misc.add_reminder("u1", "call mom", "2026-07-01 10:00", None)
    assert (await misc.get_active_reminders())[0]["message"] == "call mom"
    upd = await misc.update_reminder(r["id"], message="call dad")
    assert upd["message"] == "call dad"
    assert await misc.deactivate_reminder(r["id"]) is True
    assert await misc.get_active_reminders() == []


async def test_briefings_and_blocklist(db):
    b = await misc.add_briefing("u1", "tech,science", "0 8 * * *", num_news=3)
    assert (await misc.get_briefing(b["id"]))["num_news"] == 3
    assert await misc.add_news_block("u1", "Spam.com") is True
    assert "spam.com" in await misc.get_news_blocks("u1")
    assert await misc.remove_news_block("u1", "spam.com") is True


async def test_error_log(db):
    await misc.add_error_log("engine", "error", "boom", "trace")
    logs = await misc.get_error_logs()
    assert logs[0]["message"] == "boom"
    assert await misc.clear_error_logs() == 1
