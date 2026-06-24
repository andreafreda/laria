"""Telegram channel tests: message handling with stubs (no network)."""
from __future__ import annotations

from laria.channels.telegram import handle_update


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


async def test_text_message_runs_engine_and_replies():
    engine, client = StubEngine("hello"), StubClient()
    handled = await handle_update(_text_update(42, "hi"), engine, client)

    assert handled is True
    assert engine.calls == [("42", "hi", {})]  # chat id becomes the user id
    assert client.sent == [(42, "hello")]


async def test_non_message_update_is_ignored():
    engine, client = StubEngine(), StubClient()
    handled = await handle_update({"update_id": 2, "edited_channel_post": {}},
                                  engine, client)
    assert handled is False
    assert engine.calls == [] and client.sent == []


async def test_empty_text_is_ignored():
    engine, client = StubEngine(), StubClient()
    handled = await handle_update(_text_update(42, "   "), engine, client)
    assert handled is False
    assert engine.calls == []
