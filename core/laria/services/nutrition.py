"""Look up nutrition values for a food from free sources, cached on the DB.

Order of attempts:
  1. local cache (food_cache), instant, no network
  2. OpenFoodFacts, by barcode for packaged products or by name
  3. USDA FoodData Central, for raw foods (DEMO_KEY works but is rate-limited)
  4. nothing found, return None so the caller (or the model) can estimate

Values are normalized per 100 g: kcal, protein_g, carbs_g, fat_g. The response
parsing is kept in pure functions; the async functions add cache and network.
"""
from __future__ import annotations

import logging

import aiohttp

from ..config import get_settings
from ..storage.food import get_food_cache, set_food_cache

logger = logging.getLogger(__name__)

_OFF_PRODUCT = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
_OFF_SEARCH = "https://world.openfoodfacts.org/cgi/search.pl"
_USDA_SEARCH = "https://api.nal.usda.gov/fdc/v1/foods/search"
_TIMEOUT = aiohttp.ClientTimeout(total=8)


def parse_off_nutriments(nutriments: dict) -> dict | None:
    """Pull per-100g values out of an OpenFoodFacts nutriments block.

    Returns None when there is no energy value, since a row without calories is
    not useful for meal logging.
    """
    kcal = nutriments.get("energy-kcal_100g")
    if kcal is None:
        return None
    return {
        "kcal": round(float(kcal), 1),
        "protein_g": round(float(nutriments.get("proteins_100g", 0) or 0), 1),
        "carbs_g": round(float(nutriments.get("carbohydrates_100g", 0) or 0), 1),
        "fat_g": round(float(nutriments.get("fat_100g", 0) or 0), 1),
        "per": "100g",
    }


def parse_usda_food(food: dict) -> dict | None:
    """Pull per-100g values out of a USDA food record. None if it has no kcal."""
    values: dict[str, float] = {}
    for nutrient in food.get("foodNutrients", []):
        name = (nutrient.get("nutrientName") or "").lower()
        value = nutrient.get("value")
        if value is None:
            continue
        if "energy" in name and (nutrient.get("unitName") or "").lower() == "kcal":
            values["kcal"] = value
        elif name == "protein":
            values["protein_g"] = value
        elif "carbohydrate" in name:
            values["carbs_g"] = value
        elif name.startswith("total lipid"):
            values["fat_g"] = value
    if "kcal" not in values:
        return None
    return {
        "name": food.get("description", ""),
        "kcal": round(values.get("kcal", 0), 1),
        "protein_g": round(values.get("protein_g", 0), 1),
        "carbs_g": round(values.get("carbs_g", 0), 1),
        "fat_g": round(values.get("fat_g", 0), 1),
        "per": "100g",
    }


async def lookup_barcode(code: str) -> dict | None:
    """Nutrition for a packaged product by barcode (OpenFoodFacts), cached."""
    cache_key = f"barcode:{code}"
    cached = await get_food_cache(cache_key)
    if cached:
        return cached

    data = await _get_json(_OFF_PRODUCT.format(code=code))
    if not data or data.get("status") != 1:
        return None
    product = data.get("product", {})
    nutrition = parse_off_nutriments(product.get("nutriments", {}))
    if not nutrition:
        return None
    nutrition["name"] = product.get("product_name") or product.get("generic_name") or code
    nutrition["brand"] = product.get("brands", "")
    await set_food_cache(cache_key, nutrition, "openfoodfacts")
    return nutrition


async def lookup_food(query: str) -> dict | None:
    """Per-100g values for a food by name, or None if no source has it.

    Tries the cache, then OpenFoodFacts, then USDA, and caches a hit.
    """
    cache_key = f"food:{query.strip().lower()}"
    cached = await get_food_cache(cache_key)
    if cached:
        return cached

    result = await _search_openfoodfacts(query) or await _search_usda(query)
    if result:
        await set_food_cache(cache_key, result, result.get("_source", "api"))
    return result


async def _search_openfoodfacts(query: str) -> dict | None:
    params = {"search_terms": query, "json": 1, "page_size": 1,
              "fields": "product_name,nutriments"}
    data = await _get_json(_OFF_SEARCH, params=params)
    products = (data or {}).get("products") or []
    if not products:
        return None
    nutrition = parse_off_nutriments(products[0].get("nutriments", {}))
    if nutrition:
        nutrition["name"] = products[0].get("product_name") or query
    return nutrition


async def _search_usda(query: str) -> dict | None:
    params = {"query": query, "pageSize": 1, "api_key": get_settings().usda_api_key}
    data = await _get_json(_USDA_SEARCH, params=params)
    foods = (data or {}).get("foods") or []
    if not foods:
        return None
    nutrition = parse_usda_food(foods[0])
    if nutrition and not nutrition.get("name"):
        nutrition["name"] = query
    return nutrition


async def _get_json(url: str, params: dict | None = None) -> dict | None:
    """GET a JSON endpoint, returning None on any network or decode failure.

    Nutrition lookups are best-effort enrichment, so a flaky source must never
    break a meal log; the caller treats None as "no data".
    """
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(url, params=params) as resp:
                return await resp.json()
    except (aiohttp.ClientError, TimeoutError) as error:
        logger.warning("nutrition lookup failed for %s: %s", url, error)
        return None
