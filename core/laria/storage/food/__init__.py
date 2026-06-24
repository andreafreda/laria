"""Food domain storage: diet profiles, weight, meals, weekly plan, hydration,
shopping list, pantry and the nutrition cache.

Split into one module per concept; this package re-exports the whole public API
so callers keep using a single namespace:

    from laria.storage import food
    await food.add_meal(...)
    await food.get_shopping_list(...)

``member`` is a free-text family-member identifier (no hardcoded members).
"""
from __future__ import annotations

from .cache import CACHE_TTL_DAYS as FOOD_CACHE_TTL_DAYS
from .cache import get_food_cache, set_food_cache
from .hydration import add_hydration, delete_last_hydration, get_hydration_day
from .meals import (
    add_meal,
    delete_meal,
    export_meals,
    get_day_totals,
    get_logged_days,
    get_meals,
    list_members_with_meals,
    update_meal,
)
from .pantry import (
    add_pantry_items,
    clear_pantry,
    consume_pantry_item,
    get_pantry,
    get_pantry_expiring,
    update_pantry_item,
)
from .plan import delete_plan_meal, get_meal_plan, set_plan_meal
from .profiles import delete_profile, get_profile, list_profiles, upsert_profile
from .shopping import (
    add_shopping_items,
    check_shopping_item,
    clear_shopping_list,
    get_shopping_cost,
    get_shopping_list,
    remove_shopping_item,
    set_shopping_price,
    toggle_shopping_item,
)
from .weight import (
    add_weight,
    delete_weight,
    get_weight_history,
    get_weight_stats,
    update_weight,
)

__all__ = [
    # profiles
    "get_profile", "delete_profile", "upsert_profile", "list_profiles",
    # weight
    "add_weight", "get_weight_history", "update_weight", "delete_weight", "get_weight_stats",
    # meals
    "add_meal", "update_meal", "delete_meal", "get_meals", "get_logged_days",
    "get_day_totals", "export_meals", "list_members_with_meals",
    # plan
    "set_plan_meal", "delete_plan_meal", "get_meal_plan",
    # hydration
    "add_hydration", "delete_last_hydration", "get_hydration_day",
    # shopping
    "add_shopping_items", "get_shopping_list", "set_shopping_price",
    "remove_shopping_item", "get_shopping_cost", "check_shopping_item",
    "toggle_shopping_item", "clear_shopping_list",
    # pantry
    "add_pantry_items", "get_pantry", "get_pantry_expiring",
    "consume_pantry_item", "update_pantry_item", "clear_pantry",
    # nutrition cache
    "get_food_cache", "set_food_cache", "FOOD_CACHE_TTL_DAYS",
]
