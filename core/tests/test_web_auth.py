"""Web auth endpoint tests (login, change password) on a temp DB."""
from __future__ import annotations

import os

import pytest
from aiohttp.test_utils import TestClient, TestServer

from laria import auth
from laria.config import reload_settings
from laria.storage import init_db
from laria.web import create_app


@pytest.fixture
async def client(tmp_path):
    os.environ["LARIA_DB_PATH"] = str(tmp_path / "test.db")
    os.environ["LARIA_DATA_DIR"] = str(tmp_path)
    os.environ["LARIA_JWT_SECRET"] = "test-secret"
    os.environ["LARIA_ADMIN_USER"] = "owner"
    os.environ["LARIA_ADMIN_PASSWORD"] = "owner-pass-123"
    reload_settings()
    await init_db()
    await auth.ensure_owner()

    test_client = TestClient(TestServer(create_app(engine=None)))
    await test_client.start_server()
    yield test_client

    await test_client.close()
    for key in ("LARIA_DB_PATH", "LARIA_DATA_DIR", "LARIA_JWT_SECRET",
                "LARIA_ADMIN_USER", "LARIA_ADMIN_PASSWORD"):
        os.environ.pop(key, None)
    reload_settings()


async def test_login_success(client):
    resp = await client.post("/api/auth/login",
                             json={"username": "owner", "password": "owner-pass-123"})
    assert resp.status == 200
    body = await resp.json()
    assert auth.verify_token(body["token"])["role"] == "owner"
    assert body["must_change"] is False


async def test_login_bad_credentials(client):
    resp = await client.post("/api/auth/login",
                             json={"username": "owner", "password": "wrong"})
    assert resp.status == 401


async def test_change_password_requires_auth(client):
    resp = await client.post("/api/auth/change-password", json={"new_password": "x" * 8})
    assert resp.status == 401


async def test_change_password_then_login(client):
    login = await client.post("/api/auth/login",
                              json={"username": "owner", "password": "owner-pass-123"})
    token = (await login.json())["token"]

    changed = await client.post(
        "/api/auth/change-password", json={"new_password": "brand-new-pass"},
        headers={"Authorization": f"Bearer {token}"})
    assert changed.status == 200

    relogin = await client.post("/api/auth/login",
                                json={"username": "owner", "password": "brand-new-pass"})
    assert relogin.status == 200
