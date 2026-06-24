"""Food + utilities storage tests on a temp DB (no network)."""
from __future__ import annotations

import os

import pytest

from laria.config import reload_settings
from laria.storage import food, init_db, utilities


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


async def test_profile_upsert(db):
    await food.upsert_profile("sam", {"sex": "m", "age": 30, "kcal_target": 2200})
    p = await food.get_profile("sam")
    assert p["age"] == 30 and p["kcal_target"] == 2200
    await food.upsert_profile("sam", {"age": 31})
    assert (await food.get_profile("sam"))["age"] == 31
    assert await food.delete_profile("sam") is True


async def test_meals_and_day_totals(db):
    totals = {"kcal_total": 600, "protein_g": 30, "carbs_g": 70, "fat_g": 20}
    items = [{"name": "pasta", "grams": 100, "kcal": 350}]
    await food.add_meal("sam", "lunch", "pasta meal", totals, items,
                        eaten_at="2026-02-01 13:00:00", logged_by="sam")
    day = await food.get_day_totals("sam", "2026-02-01")
    assert day["kcal"] == 600.0 and day["meals"] == 1
    meals = await food.get_meals("sam", "2026-02-01", "2026-02-01")
    assert len(meals) == 1


async def test_weight_stats(db):
    await food.add_weight("sam", 80.0, 24.0)
    await food.add_weight("sam", 79.0, 23.7)
    stats = await food.get_weight_stats("sam")
    assert stats["count"] == 2
    assert stats["latest"] == 79.0


async def test_shopping_and_pantry(db):
    await food.add_shopping_items([{"name": "milk", "qty": "2", "price": 1.5},
                                   {"name": "bread", "price": 2.0}])
    lst = await food.get_shopping_list()
    assert len(lst) == 2
    cost = await food.get_shopping_cost()
    assert cost["total"] == 3.5
    assert await food.check_shopping_item("milk") is True
    assert len(await food.get_shopping_list()) == 1  # checked hidden

    await food.add_pantry_items([{"name": "rice", "expires_on": "2026-01-01"}])
    assert len(await food.get_pantry()) == 1
    assert await food.consume_pantry_item("rice") == 1


async def test_meal_plan(db):
    await food.set_plan_meal("2026-03-01", "dinner", "soup", recipe="boil")
    plan = await food.get_meal_plan("2026-03-01", "2026-03-07")
    assert plan[0]["items"] == "soup"
    assert await food.delete_plan_meal("2026-03-01", "dinner") == 1


async def test_hydration(db):
    await food.add_hydration("sam", 500)
    await food.add_hydration("sam", 250)
    import datetime
    today = datetime.date.today().isoformat()
    h = await food.get_hydration_day("sam", today)
    assert h["ml_total"] == 750.0 and h["count"] == 2


async def test_utility_bills(db):
    assert await utilities.bills_empty() is True
    await utilities.set_bill("power", "kwh", 2026, 1, 120.0)
    await utilities.set_bill("power", "cost", 2026, 1, 45.0)
    assert await utilities.bills_empty() is False
    csv = await utilities.get_bill_csv("power", "kwh", 2026)
    assert csv.startswith("120,")
    assert 2026 in await utilities.get_bill_years("power", "kwh")


async def test_utility_bill_range(db):
    await utilities.set_bill_range("gas", "cost", 2026, 1, 4, 100.0)
    existing = await utilities.get_bill_existing_range("gas", "cost", 2026, 1, 4)
    assert len(existing) == 4
    assert round(sum(v for _, v in existing), 1) == 100.0  # remainder absorbed
