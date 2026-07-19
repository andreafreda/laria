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


async def test_claim_links_owner_chat(db):
    os.environ["LARIA_TELEGRAM_CLAIM_CODE"] = "secret123"
    os.environ["LARIA_ADMIN_USER"] = "owner"
    reload_settings()
    owner_id = await identity.create_user("owner", "h", role="owner")
    engine, client = StubEngine(), StubClient()

    handled = await handle_update(_text_update(500, "/claim secret123"), engine, client)

    assert handled is True
    assert (await identity.get_user_by_telegram("500"))["id"] == owner_id
    assert "now linked" in client.sent[0][1]
    # after claiming, a normal message runs the engine as the owner
    await handle_update(_text_update(500, "hi"), engine, client)
    assert engine.calls[-1][0] == str(owner_id)
    os.environ.pop("LARIA_TELEGRAM_CLAIM_CODE", None)
    os.environ.pop("LARIA_ADMIN_USER", None)
    reload_settings()


async def test_claim_wrong_code_is_refused(db):
    os.environ["LARIA_TELEGRAM_CLAIM_CODE"] = "secret123"
    os.environ["LARIA_ADMIN_USER"] = "owner"
    reload_settings()
    await identity.create_user("owner", "h", role="owner")
    engine, client = StubEngine(), StubClient()

    handled = await handle_update(_text_update(500, "/claim nope"), engine, client)

    assert handled is False
    assert "not linked" in client.sent[0][1]
    assert await identity.get_user_by_telegram("500") is None
    os.environ.pop("LARIA_TELEGRAM_CLAIM_CODE", None)
    os.environ.pop("LARIA_ADMIN_USER", None)
    reload_settings()


async def test_reset_command_sets_temp_password(db):
    os.environ["LARIA_JWT_SECRET"] = "test-secret"
    reload_settings()
    from laria import auth
    uid = await auth.create_user_account("dave", "old-pass-12")
    await identity.link_telegram(uid, "77")
    engine, client = StubEngine(), StubClient()

    handled = await handle_update(_text_update(77, "/reset"), engine, client)

    assert handled is True
    assert engine.calls == []  # a command does not reach the engine
    message = client.sent[0][1]
    assert "Temporary password:" in message
    temp = message.split("Temporary password:")[1].split()[0]
    # the temp password works and the user is flagged to change it
    assert await auth.authenticate("dave", temp)
    assert (await identity.get_user_by_id(uid))["must_change_password"] is True
    os.environ.pop("LARIA_JWT_SECRET", None)
