"""News briefing and system log endpoint tests on a temp DB."""
from __future__ import annotations

import os

import pytest
from aiohttp.test_utils import TestClient, TestServer

from laria import auth
from laria.config import reload_settings
from laria.storage import init_db, misc
from laria.web import create_app


def _auth_header(role: str = "owner", user_id: int = 1) -> dict:
    user = {"id": user_id, "username": "u", "role": role,
            "profile_id": 1, "must_change_password": False}
    return {"Authorization": f"Bearer {auth.issue_token(user)}"}


@pytest.fixture
async def client(tmp_path):
    os.environ["LARIA_DB_PATH"] = str(tmp_path / "test.db")
    os.environ["LARIA_DATA_DIR"] = str(tmp_path)
    os.environ["LARIA_JWT_SECRET"] = "test-secret"
    reload_settings()
    await init_db()
    test_client = TestClient(TestServer(create_app(engine=None)))
    await test_client.start_server()
    yield test_client
    await test_client.close()
    for key in ("LARIA_DB_PATH", "LARIA_DATA_DIR", "LARIA_JWT_SECRET"):
        os.environ.pop(key, None)
    reload_settings()


async def test_briefing_create_list_delete(client):
    headers = _auth_header()
    created = await (await client.post("/api/news/briefings", headers=headers, json={
        "topics": [{"topic": "ai", "sources": ["wired.com"]}],
        "cron": "0 8 * * *", "num_news": 4,
    })).json()
    assert created["cron"] == "0 8 * * *"

    listing = await (await client.get("/api/news/briefings", headers=headers)).json()
    assert listing[0]["topics"] == [{"topic": "ai", "sources": ["wired.com"]}]

    deleted = await (await client.post(
        "/api/news/briefings/delete", headers=headers, json={"id": created["id"]})).json()
    assert deleted["ok"] is True
    assert await (await client.get("/api/news/briefings", headers=headers)).json() == []


async def test_create_briefing_requires_cron(client):
    resp = await client.post("/api/news/briefings", headers=_auth_header(),
                             json={"topics": [{"topic": "ai"}]})
    assert resp.status == 400


async def test_unhandled_error_is_logged_and_returns_500(client):
    headers = _auth_header()
    # A non-numeric year makes the trend handler raise; the error middleware
    # should turn it into a 500 and record it for the System log page.
    resp = await client.get("/api/finance/trend?year=notanumber", headers=headers)
    assert resp.status == 500

    logs = await (await client.get("/api/system/logs", headers=headers)).json()
    assert any(entry["source"] == "web" for entry in logs)


async def test_system_logs_owner_only(client):
    await misc.add_error_log("test", "error", "boom", None)
    assert (await client.get("/api/system/logs", headers=_auth_header(role="adult"))).status == 403

    logs = await (await client.get("/api/system/logs", headers=_auth_header())).json()
    assert logs[0]["message"] == "boom"

    cleared = await (await client.post("/api/system/logs/clear", headers=_auth_header())).json()
    assert cleared["deleted"] == 1
