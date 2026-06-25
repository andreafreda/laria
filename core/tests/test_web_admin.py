"""Admin API tests: owner-only management of profiles, users, guardianships."""
from __future__ import annotations

import os

import pytest
from aiohttp.test_utils import TestClient, TestServer

from laria import auth
from laria.config import reload_settings
from laria.storage import identity, init_db
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


async def _owner_header(client) -> dict:
    resp = await client.post("/api/auth/login",
                             json={"username": "owner", "password": "owner-pass-123"})
    token = (await resp.json())["token"]
    return {"Authorization": f"Bearer {token}"}


def _adult_header() -> dict:
    token = auth.issue_token({"id": 99, "username": "kid", "role": "adult",
                              "profile_id": 1, "must_change_password": False})
    return {"Authorization": f"Bearer {token}"}


async def test_admin_requires_owner_role(client):
    resp = await client.get("/api/admin/users", headers=_adult_header())
    assert resp.status == 403


async def test_admin_requires_auth(client):
    resp = await client.get("/api/admin/users")
    assert resp.status == 401


async def test_list_users_hides_password_hash(client):
    resp = await client.get("/api/admin/users", headers=await _owner_header(client))
    users = await resp.json()
    assert users[0]["username"] == "owner"
    assert "password_hash" not in users[0]


async def test_create_profile_and_user_and_login(client):
    headers = await _owner_header(client)
    profile = await (await client.post(
        "/api/admin/profiles", json={"name": "Marina"}, headers=headers)).json()
    created = await (await client.post(
        "/api/admin/users",
        json={"username": "marina", "password": "marina-pass-1", "role": "adult",
              "profile_id": profile["id"]},
        headers=headers)).json()
    assert created["username"] == "marina"

    login = await client.post("/api/auth/login",
                              json={"username": "marina", "password": "marina-pass-1"})
    assert login.status == 200


async def test_reset_password(client):
    headers = await _owner_header(client)
    await client.post("/api/admin/profiles", json={"name": "Bob"}, headers=headers)
    user_id = (await (await client.post(
        "/api/admin/users",
        json={"username": "bob", "password": "bob-pass-12"}, headers=headers)).json())["id"]

    resp = await client.post("/api/admin/users/reset-password",
                             json={"user_id": user_id, "new_password": "fresh-pass-9"},
                             headers=headers)
    assert resp.status == 200
    login = await client.post("/api/auth/login",
                              json={"username": "bob", "password": "fresh-pass-9"})
    assert login.status == 200


async def test_guardianship_and_telegram_link(client):
    headers = await _owner_header(client)
    child = await (await client.post(
        "/api/admin/profiles", json={"name": "Kid", "is_dependent": True},
        headers=headers)).json()
    owner_id = (await identity.get_user_by_username("owner"))["id"]

    g = await client.post("/api/admin/guardianships",
                          json={"guardian_user_id": owner_id, "profile_id": child["id"]},
                          headers=headers)
    assert g.status == 200
    assert await identity.is_guardian(owner_id, child["id"]) is True

    t = await client.post("/api/admin/users/link-telegram",
                          json={"user_id": owner_id, "chat_id": "555"}, headers=headers)
    assert t.status == 200
    assert (await identity.get_user_by_telegram("555"))["id"] == owner_id
