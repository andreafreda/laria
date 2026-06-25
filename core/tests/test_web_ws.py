"""WebSocket chat endpoint tests with a stub engine (no network)."""
from __future__ import annotations

import os

import pytest
from aiohttp.test_utils import TestClient, TestServer

from laria import auth
from laria.config import reload_settings
from laria.web import create_app


class StubEngine:
    def __init__(self, reply="pong"):
        self.reply = reply
        self.calls: list[tuple] = []

    async def chat(self, user_id, text, user_config):
        self.calls.append((user_id, text, user_config))
        return self.reply


@pytest.fixture(autouse=True)
def jwt_secret():
    os.environ["LARIA_JWT_SECRET"] = "test-secret"
    reload_settings()
    yield
    os.environ.pop("LARIA_JWT_SECRET", None)
    reload_settings()


def _token() -> str:
    return auth.issue_token({"id": 5, "username": "alice", "role": "owner",
                             "profile_id": 1, "must_change_password": False})


async def _client(engine) -> TestClient:
    client = TestClient(TestServer(create_app(engine)))
    await client.start_server()
    return client


async def test_ws_chat_roundtrip():
    engine = StubEngine("hello")
    client = await _client(engine)
    try:
        ws = await client.ws_connect(f"/api/chat/ws?token={_token()}")
        await ws.send_json({"text": "hi"})
        reply = await ws.receive_json()
        assert reply == {"reply": "hello"}
        assert engine.calls == [("5", "hi", {})]  # user id from the token
        await ws.close()
    finally:
        await client.close()


async def test_ws_rejects_missing_token():
    client = await _client(StubEngine())
    try:
        resp = await client.get("/api/chat/ws")  # no token, no upgrade
        assert resp.status == 401
    finally:
        await client.close()


async def test_ws_reports_empty_text():
    client = await _client(StubEngine())
    try:
        ws = await client.ws_connect(f"/api/chat/ws?token={_token()}")
        await ws.send_json({"text": "  "})
        assert "error" in await ws.receive_json()
        await ws.close()
    finally:
        await client.close()
