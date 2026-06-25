"""Food endpoint tests (plan, diary, profiles, shopping, pantry) on a temp DB."""
from __future__ import annotations

import os
from datetime import date

import pytest
from aiohttp.test_utils import TestClient, TestServer

from laria import auth
from laria.config import reload_settings
from laria.storage import food, init_db
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
    today = date.today().isoformat()
    await food.upsert_profile("sam", {"kcal_target": 2000, "weight_kg": 70})
    await food.add_meal("sam", "lunch", "rice", {"kcal_total": 600}, [],
                        f"{today} 12:00:00", None)
    await food.set_plan_meal(today, "dinner", "pasta")
    await food.add_shopping_items([{"name": "milk"}, {"name": "bread"}])
    await food.add_pantry_items([{"name": "rice", "expires_on": "2099-01-01"}])

    test_client = TestClient(TestServer(create_app(engine=None)))
    await test_client.start_server()
    yield test_client

    await test_client.close()
    for key in ("LARIA_DB_PATH", "LARIA_DATA_DIR", "LARIA_JWT_SECRET"):
        os.environ.pop(key, None)
    reload_settings()


async def test_food_requires_auth(client):
    resp = await client.get("/api/food/plan")
    assert resp.status == 401


async def test_plan(client):
    resp = await client.get("/api/food/plan", headers=_auth_header())
    plan = await resp.json()
    assert any(m["items"] == "pasta" for m in plan)


async def test_diary_includes_member_with_macros(client):
    today = date.today().isoformat()
    resp = await client.get(f"/api/food/diary?date={today}", headers=_auth_header())
    diary = await resp.json()
    entry = diary["members"][0]
    assert entry["member"] == "sam"
    assert entry["totals"]["kcal"] == 600.0
    assert entry["macro_targets"]["protein_target_g"] == 112.0  # 1.6 * 70


async def test_profiles_carry_macro_targets(client):
    resp = await client.get("/api/food/profiles", headers=_auth_header())
    profiles = await resp.json()
    assert profiles[0]["macro_targets"]["protein_target_g"] == 112.0


async def test_shopping_list_and_toggle(client):
    headers = _auth_header()
    listing = await (await client.get("/api/food/shopping", headers=headers)).json()
    assert len(listing["items"]) == 2
    item_id = listing["items"][0]["id"]

    toggled = await (await client.post(
        "/api/food/shopping/toggle", json={"id": item_id}, headers=headers)).json()
    assert toggled["ok"] is True


async def test_pantry(client):
    resp = await client.get("/api/food/pantry", headers=_auth_header())
    pantry = await resp.json()
    assert any(i["name"] == "rice" for i in pantry["items"])
