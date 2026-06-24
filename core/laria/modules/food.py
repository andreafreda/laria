"""Food tools the assistant can call during a conversation.

Thin bridges between the language model and ``storage.food``: meals, weight,
hydration, the shopping list and the pantry. Register them on an engine's tool
registry with ``register_food_tools``.

Handlers return a string: JSON for data the model should reason over, or a plain
sentence to confirm an action. ``member`` is the family member the entry is
about (free text), kept explicit because it differs from the chat user.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from ..engine.tools import Tool, ToolContext, ToolRegistry
from ..storage import food


async def _log_meal(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Record a meal with its optional nutrition totals and confirm it."""
    totals = {
        "kcal_total": inputs.get("kcal"),
        "protein_g": inputs.get("protein_g"),
        "carbs_g": inputs.get("carbs_g"),
        "fat_g": inputs.get("fat_g"),
    }
    await food.add_meal(
        member=inputs["member"],
        meal_type=inputs["meal_type"],
        description=inputs["description"],
        totals=totals,
        items=inputs.get("items", []),
        eaten_at=inputs.get("eaten_at"),
        logged_by=ctx.user_id,
    )
    return f"Logged {inputs['meal_type']} for {inputs['member']}: {inputs['description']}."


async def _day_totals(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Return a member's nutrition totals for a day (defaults to today) as JSON."""
    day = inputs.get("day") or date.today().isoformat()
    return json.dumps(await food.get_day_totals(inputs["member"], day), ensure_ascii=False)


async def _log_weight(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Record a weight measurement for a member and confirm it."""
    await food.add_weight(inputs["member"], float(inputs["weight_kg"]), inputs.get("bmi"))
    return f"Logged {inputs['weight_kg']} kg for {inputs['member']}."


async def _log_hydration(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Record a drink (in ml) for a member and confirm it."""
    await food.add_hydration(inputs["member"], float(inputs["ml"]))
    return f"Logged {inputs['ml']} ml for {inputs['member']}."


async def _add_shopping_items(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Add items to the shopping list and report how many were added."""
    added = await food.add_shopping_items(inputs["items"])
    return f"Added {added} item(s) to the shopping list."


async def _get_shopping_list(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Return the shopping list as JSON (unchecked items by default)."""
    include_checked = bool(inputs.get("include_checked", False))
    return json.dumps(await food.get_shopping_list(include_checked), ensure_ascii=False)


async def _check_shopping_item(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Tick off matching shopping items as bought and confirm."""
    ticked = await food.check_shopping_item(inputs["name"])
    return ("Checked off." if ticked
            else f"No unchecked item matching '{inputs['name']}'.")


async def _add_pantry_items(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Add items to the pantry and report how many were added."""
    added = await food.add_pantry_items(inputs["items"])
    return f"Added {added} item(s) to the pantry."


async def _get_pantry(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Return pantry contents as JSON, optionally one category."""
    return json.dumps(await food.get_pantry(inputs.get("category")), ensure_ascii=False)


async def _pantry_expiring(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Return pantry items expiring within N days (default 3) as JSON."""
    within_days = int(inputs.get("within_days", 3))
    return json.dumps(await food.get_pantry_expiring(within_days), ensure_ascii=False)


_MEMBER = {"type": "string", "description": "Family member the entry is about"}
_ITEM_LIST = {
    "type": "array",
    "items": {"type": "object"},
    "description": "Each item: name (required), plus optional qty, category, ...",
}


def register_food_tools(registry: ToolRegistry) -> None:
    """Add the food tools to a registry so the engine exposes them to the model."""
    registry.register(Tool(
        name="log_meal",
        description=("Record a meal a member ate. Nutrition totals (kcal, "
                     "protein_g, carbs_g, fat_g) are optional. eaten_at is a "
                     "datetime, defaulting to now."),
        input_schema={
            "type": "object",
            "properties": {
                "member": _MEMBER,
                "meal_type": {"type": "string", "description": "breakfast, lunch, dinner, snack"},
                "description": {"type": "string", "description": "What was eaten"},
                "kcal": {"type": "number"},
                "protein_g": {"type": "number"},
                "carbs_g": {"type": "number"},
                "fat_g": {"type": "number"},
                "eaten_at": {"type": "string", "description": "Datetime (defaults to now)"},
            },
            "required": ["member", "meal_type", "description"],
        },
        handler=_log_meal,
    ))
    registry.register(Tool(
        name="get_day_totals",
        description="Get a member's calorie and nutrient totals for a day.",
        input_schema={
            "type": "object",
            "properties": {
                "member": _MEMBER,
                "day": {"type": "string", "description": "YYYY-MM-DD (defaults to today)"},
            },
            "required": ["member"],
        },
        handler=_day_totals,
    ))
    registry.register(Tool(
        name="log_weight",
        description="Record a weight measurement (kg) for a member.",
        input_schema={
            "type": "object",
            "properties": {
                "member": _MEMBER,
                "weight_kg": {"type": "number"},
                "bmi": {"type": "number", "description": "Optional, if known"},
            },
            "required": ["member", "weight_kg"],
        },
        handler=_log_weight,
    ))
    registry.register(Tool(
        name="log_hydration",
        description="Record how much a member drank, in millilitres.",
        input_schema={
            "type": "object",
            "properties": {"member": _MEMBER, "ml": {"type": "number"}},
            "required": ["member", "ml"],
        },
        handler=_log_hydration,
    ))
    registry.register(Tool(
        name="add_shopping_items",
        description="Add one or more items to the shopping list.",
        input_schema={
            "type": "object",
            "properties": {"items": _ITEM_LIST},
            "required": ["items"],
        },
        handler=_add_shopping_items,
    ))
    registry.register(Tool(
        name="get_shopping_list",
        description="Get the shopping list (unchecked items unless include_checked).",
        input_schema={
            "type": "object",
            "properties": {
                "include_checked": {"type": "boolean", "description": "Include bought items too"},
            },
        },
        handler=_get_shopping_list,
    ))
    registry.register(Tool(
        name="check_shopping_item",
        description="Mark a shopping item as bought (partial name match).",
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        handler=_check_shopping_item,
    ))
    registry.register(Tool(
        name="add_pantry_items",
        description="Add one or more items to the pantry (each may have expires_on).",
        input_schema={
            "type": "object",
            "properties": {"items": _ITEM_LIST},
            "required": ["items"],
        },
        handler=_add_pantry_items,
    ))
    registry.register(Tool(
        name="get_pantry",
        description="List what's in the pantry, optionally one category.",
        input_schema={
            "type": "object",
            "properties": {"category": {"type": "string"}},
        },
        handler=_get_pantry,
    ))
    registry.register(Tool(
        name="pantry_expiring",
        description="List pantry items expiring soon (within N days, default 3).",
        input_schema={
            "type": "object",
            "properties": {"within_days": {"type": "integer"}},
        },
        handler=_pantry_expiring,
    ))
