"""Web API tests using a stub engine (no LLM, no network)."""
from __future__ import annotations

from aiohttp.test_utils import TestClient, TestServer

from laria.web import create_app


class StubEngine:
    """Records the last chat call and returns a canned reply."""

    def __init__(self, reply: str = "pong"):
        self.reply = reply
        self.calls: list[tuple] = []

    async def chat(self, user_id: str, text: str, user_config: dict) -> str:
        self.calls.append((user_id, text, user_config))
        return self.reply


async def _client(engine) -> TestClient:
    client = TestClient(TestServer(create_app(engine)))
    await client.start_server()
    return client


async def test_health():
    client = await _client(StubEngine())
    try:
        resp = await client.get("/health")
        assert resp.status == 200
        assert (await resp.json())["status"] == "ok"
    finally:
        await client.close()


async def test_chat_returns_reply():
    engine = StubEngine("hello there")
    client = await _client(engine)
    try:
        resp = await client.post("/api/chat", json={"user_id": "u1", "text": "hi"})
        assert resp.status == 200
        assert (await resp.json())["reply"] == "hello there"
        assert engine.calls == [("u1", "hi", {})]
    finally:
        await client.close()


async def test_chat_defaults_user_id():
    engine = StubEngine()
    client = await _client(engine)
    try:
        await client.post("/api/chat", json={"text": "hi"})
        assert engine.calls[0][0] == "default"
    finally:
        await client.close()


async def test_chat_rejects_empty_text():
    client = await _client(StubEngine())
    try:
        resp = await client.post("/api/chat", json={"text": "  "})
        assert resp.status == 400
    finally:
        await client.close()


async def test_chat_rejects_invalid_json():
    client = await _client(StubEngine())
    try:
        resp = await client.post("/api/chat", data="not json",
                                 headers={"Content-Type": "application/json"})
        assert resp.status == 400
    finally:
        await client.close()
