"""Telegram channel tests: allowlist binding + message handling (no network)."""
from __future__ import annotations

import os

import pytest

from laria.channels.telegram import handle_update
from laria.config import reload_settings
from laria.storage import identity, init_db


class StubEngine:
    def __init__(self, reply="ok"):
        self.reply = reply
        self.calls: list[tuple] = []

    async def chat(self, user_id, text, user_config):
        self.calls.append((user_id, text, user_config))
        return self.reply


class StubClient:
    def __init__(self):
        self.sent: list[tuple] = []

    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))


def _text_update(chat_id: int, text: str, update_id: int = 1) -> dict:
    return {"update_id": update_id, "message": {"text": text, "chat": {"id": chat_id}}}


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


async def test_linked_chat_runs_engine_under_user_id(db):
    uid = await identity.create_user("alice", "h")
    await identity.link_telegram(uid, "42")
    engine, client = StubEngine("hello"), StubClient()

    handled = await handle_update(_text_update(42, "hi"), engine, client)

    assert handled is True
    # engine runs as the linked user, not the raw chat id
    assert engine.calls == [(str(uid), "hi", {})]
    assert client.sent == [(42, "hello")]


async def test_unlinked_chat_is_refused(db):
    engine, client = StubEngine(), StubClient()
    handled = await handle_update(_text_update(999, "hi"), engine, client)

    assert handled is False
    assert engine.calls == []
    assert "not linked" in client.sent[0][1]


async def test_non_message_update_is_ignored(db):
    engine, client = StubEngine(), StubClient()
    handled = await handle_update({"update_id": 2, "edited_channel_post": {}},
                                  engine, client)
    assert handled is False
    assert engine.calls == [] and client.sent == []


async def test_empty_text_is_ignored(db):
    engine, client = StubEngine(), StubClient()
    handled = await handle_update(_text_update(42, "   "), engine, client)
    assert handled is False
    assert engine.calls == []
