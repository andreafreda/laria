"""Food and utilities module tests: tools wired to storage, dispatched directly."""
from __future__ import annotations

import json
import os

import pytest

from laria.config import reload_settings
from laria.engine import ToolRegistry
from laria.engine.tools import ToolContext
from laria.memory import Scope
from laria.memory.fake import FakeBackend
from laria.modules import register_food_tools, register_utilities_tools
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


def _ctx() -> ToolContext:
    return ToolContext(user_id="u1", memory=FakeBackend(), scope=Scope(user_id="u1"))


def _registry(register) -> ToolRegistry:
    registry = ToolRegistry()
    register(registry)
    return registry


async def test_food_tools_registered(db):
    names = {s["name"] for s in _registry(register_food_tools).schemas()}
    assert {"log_meal", "get_day_totals", "add_shopping_items"} <= names


async def test_log_meal_persists(db):
    registry = _registry(register_food_tools)
    await registry.dispatch("log_meal", {
        "member": "sam", "meal_type": "lunch", "description": "pasta",
        "kcal": 600, "eaten_at": "2026-02-01 13:00:00",
    }, _ctx())

    totals = json.loads(await registry.dispatch(
        "get_day_totals", {"member": "sam", "day": "2026-02-01"}, _ctx()))
    assert totals["kcal"] == 600.0


async def test_shopping_flow(db):
    registry = _registry(register_food_tools)
    await registry.dispatch("add_shopping_items",
                            {"items": [{"name": "milk"}, {"name": "bread"}]}, _ctx())
    items = json.loads(await registry.dispatch("get_shopping_list", {}, _ctx()))
    assert len(items) == 2
    await registry.dispatch("check_shopping_item", {"name": "milk"}, _ctx())
    remaining = json.loads(await registry.dispatch("get_shopping_list", {}, _ctx()))
    assert len(remaining) == 1


async def test_utilities_record_and_read(db):
    registry = _registry(register_utilities_tools)
    await registry.dispatch("record_bill", {
        "utility": "power", "metric": "kwh", "year": 2026, "month": 1, "value": 120,
    }, _ctx())

    monthly = json.loads(await registry.dispatch("get_bill_year", {
        "utility": "power", "metric": "kwh", "year": 2026,
    }, _ctx()))
    assert monthly[0] == 120.0  # January
    assert len(monthly) == 12


async def test_utilities_bill_range(db):
    registry = _registry(register_utilities_tools)
    await registry.dispatch("record_bill_range", {
        "utility": "gas", "metric": "cost", "year": 2026,
        "month_start": 1, "month_end": 4, "total": 100.0,
    }, _ctx())
    monthly = json.loads(await registry.dispatch("get_bill_year", {
        "utility": "gas", "metric": "cost", "year": 2026,
    }, _ctx()))
    assert round(sum(monthly), 1) == 100.0
