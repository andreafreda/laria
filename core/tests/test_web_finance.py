"""Finance read-model endpoint tests (the dashboard data) on a temp DB."""
from __future__ import annotations

import os

import pytest
from aiohttp.test_utils import TestClient, TestServer

from laria import auth
from laria.config import reload_settings
from laria.storage import finance, init_db
from laria.web import create_app


def _auth_header() -> dict:
    user = {"id": 1, "username": "owner", "role": "owner",
            "profile_id": 1, "must_change_password": False}
    return {"Authorization": f"Bearer {auth.issue_token(user)}"}


@pytest.fixture
async def client(tmp_path):
    os.environ["LARIA_DB_PATH"] = str(tmp_path / "test.db")
    os.environ["LARIA_DATA_DIR"] = str(tmp_path)
    os.environ["LARIA_JWT_SECRET"] = "test-secret"
    reload_settings()
    await init_db()
    await finance.add_account("checking", "bank", opening_balance=100.0)
    await finance.add_transaction("checking", "2026-01-10", -30.0, "groceries")
    await finance.add_transaction("checking", "2026-01-12", 200.0, "salary")
    await finance.set_budget("groceries", 100.0)
    await finance.set_goal("vacation", 1000.0)

    test_client = TestClient(TestServer(create_app(engine=None)))
    await test_client.start_server()
    yield test_client

    await test_client.close()
    os.environ.pop("LARIA_DB_PATH", None)
    os.environ.pop("LARIA_DATA_DIR", None)
    os.environ.pop("LARIA_JWT_SECRET", None)
    reload_settings()


async def test_read_endpoints_require_auth(client):
    resp = await client.get("/api/finance/balances")
    assert resp.status == 401


async def test_balances(client):
    resp = await client.get("/api/finance/balances", headers=_auth_header())
    balances = await resp.json()
    assert balances[0]["account"] == "checking" and balances[0]["balance"] == 270.0


async def test_summary(client):
    resp = await client.get("/api/finance/summary", headers=_auth_header())
    summary = await resp.json()
    assert summary["income"] == 200.0 and summary["expenses"] == -30.0


async def test_matrix_and_goals_and_budget(client):
    headers = _auth_header()
    matrix = await (await client.get("/api/finance/matrix", headers=headers)).json()
    assert "groceries" in matrix["categories"]

    goals = await (await client.get("/api/finance/goals", headers=headers)).json()
    assert goals[0]["name"] == "vacation"

    status = await (await client.get(
        "/api/finance/budget-status?year=2026&month=1", headers=headers)).json()
    assert status[0]["category"] == "groceries" and status[0]["spent"] == 30.0


async def test_trend_returns_twelve_months(client):
    resp = await client.get("/api/finance/trend?year=2026", headers=_auth_header())
    trend = await resp.json()
    assert len(trend) == 12
    january = next(m for m in trend if m["month"] == 1)
    assert january["income"] == 200.0 and abs(january["expenses"]) == 30.0


async def test_category_year(client):
    resp = await client.get("/api/finance/category-year?year=2026", headers=_auth_header())
    categories = await resp.json()
    assert any(c["category"] == "groceries" for c in categories)
