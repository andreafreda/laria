"""Nutrition service tests: pure parsers and the cache-hit path (no network)."""
from __future__ import annotations

import os

import pytest

from laria.config import reload_settings
from laria.services import nutrition
from laria.storage import init_db
from laria.storage.food import set_food_cache


def test_parse_off_nutriments():
    block = {"energy-kcal_100g": 52, "proteins_100g": 0.3,
             "carbohydrates_100g": 14, "fat_100g": 0.2}
    parsed = nutrition.parse_off_nutriments(block)
    assert parsed["kcal"] == 52.0 and parsed["per"] == "100g"
    assert nutrition.parse_off_nutriments({}) is None  # no energy, no use


def test_parse_usda_food():
    food = {"description": "Apple, raw", "foodNutrients": [
        {"nutrientName": "Energy", "unitName": "KCAL", "value": 52},
        {"nutrientName": "Protein", "value": 0.3},
        {"nutrientName": "Carbohydrate, by difference", "value": 14},
        {"nutrientName": "Total lipid (fat)", "value": 0.2},
    ]}
    parsed = nutrition.parse_usda_food(food)
    assert parsed["name"] == "Apple, raw"
    assert parsed["kcal"] == 52.0 and parsed["carbs_g"] == 14.0


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


async def test_lookup_food_uses_cache_without_network(db):
    # Seed the cache under the key lookup_food computes, then it must return it
    # without ever hitting the network.
    await set_food_cache("food:banana", {"kcal": 89.0, "per": "100g"}, "test")
    result = await nutrition.lookup_food("Banana")
    assert result["kcal"] == 89.0
    assert result["_source"] == "test"
