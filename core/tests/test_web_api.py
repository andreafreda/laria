"""Web API tests with a stub engine and a crafted token (no LLM, no network)."""
from __future__ import annotations

import os

import pytest
from aiohttp.test_utils import TestClient, TestServer

from laria import auth
from laria.config import reload_settings
from laria.web import create_app


class StubEngine:
    """Records the last chat call and returns a canned reply."""

    def __init__(self, reply: str = "pong"):
        self.reply = reply
        self.calls: list[tuple] = []

    async def chat(self, user_id: str, text: str, user_config: dict) -> str:
        self.calls.append((user_id, text, user_config))
        return self.reply


@pytest.fixture(autouse=True)
def jwt_secret():
    os.environ["LARIA_JWT_SECRET"] = "test-secret"
    reload_settings()
    yield
    os.environ.pop("LARIA_JWT_SECRET", None)
    reload_settings()


def _token(user_id: int = 7) -> str:
    user = {"id": user_id, "username": "alice", "role": "owner",
            "profile_id": 1, "must_change_password": False}
    return auth.issue_token(user)


def _auth_header() -> dict:
    return {"Authorization": f"Bearer {_token()}"}


async def _client(engine) -> TestClient:
    client = TestClient(TestServer(create_app(engine)))
    await client.start_server()
    return client


async def test_health_is_public():
    client = await _client(StubEngine())
    try:
        resp = await client.get("/health")
        assert resp.status == 200
    finally:
        await client.close()


async def test_chat_requires_auth():
    client = await _client(StubEngine())
    try:
        resp = await client.post("/api/chat", json={"text": "hi"})
        assert resp.status == 401
    finally:
        await client.close()


async def test_chat_uses_identity_from_token():
    engine = StubEngine("hello there")
    client = await _client(engine)
    try:
        resp = await client.post("/api/chat", json={"text": "hi"}, headers=_auth_header())
        assert resp.status == 200
        assert (await resp.json())["reply"] == "hello there"
        # user id comes from the token (sub=7), never from the body
        assert engine.calls == [("7", "hi", {})]
    finally:
        await client.close()


async def test_chat_rejects_empty_text():
    client = await _client(StubEngine())
    try:
        resp = await client.post("/api/chat", json={"text": "  "}, headers=_auth_header())
        assert resp.status == 400
    finally:
        await client.close()


async def test_chat_rejects_invalid_json():
    client = await _client(StubEngine())
    try:
        resp = await client.post("/api/chat", data="not json", headers={
            **_auth_header(), "Content-Type": "application/json"})
        assert resp.status == 400
    finally:
        await client.close()
