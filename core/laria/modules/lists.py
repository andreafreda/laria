"""Generic list tools the assistant can call during a conversation.

Lets the bot manage free-form lists (todo, checklist, packing, and a generic
shopping kind separate from the food pantry/shopping domain): create a list, add
and check off items, read a list, remove items. Lists and items are addressed by
name, the way a user refers to them in chat, so the handlers resolve a name to an
id and create a list on first use when adding to one that does not exist yet.
"""
from __future__ import annotations

import json
from typing import Any

from ..engine.tools import Tool, ToolContext, ToolRegistry
from ..storage import lists


async def _resolve_list_id(name: str) -> int | None:
    """Find a list id by name (case-insensitive), or None when there is no match."""
    target = (name or "").strip().lower()
    for entry in await lists.get_lists():
        if entry["name"].lower() == target:
            return entry["id"]
    return None


async def _resolve_item_id(list_id: int, text: str) -> int | None:
    """Find an item id within a list by its text (case-insensitive)."""
    target = (text or "").strip().lower()
    for item in await lists.get_list_items(list_id):
        if item["text"].lower() == target:
            return item["id"]
    return None


async def _create_list(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Create a new named list of a given kind and confirm it."""
    created = await lists.create_list(inputs["name"], inputs.get("kind", "todo"))
    return json.dumps({"ok": True, "list": created}, ensure_ascii=False)


async def _show_lists(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Return every list with its open-item count."""
    return json.dumps(await lists.get_lists(), ensure_ascii=False)


async def _add_item(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Add an item to a list, creating the list if it does not exist yet."""
    list_id = await _resolve_list_id(inputs["list"])
    if list_id is None:
        list_id = (await lists.create_list(inputs["list"], inputs.get("kind", "todo")))["id"]
    item = await lists.add_list_item(list_id, inputs["item"],
                                     inputs.get("qty"), inputs.get("due_at"))
    return json.dumps({"ok": True, "added": item}, ensure_ascii=False)


async def _show_list(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Return the items of a named list."""
    list_id = await _resolve_list_id(inputs["list"])
    if list_id is None:
        return f"List '{inputs['list']}' not found."
    return json.dumps(await lists.get_list_items(list_id), ensure_ascii=False)


async def _check_item(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Tick an item off a list (toggles its checked state)."""
    list_id = await _resolve_list_id(inputs["list"])
    if list_id is None:
        return f"List '{inputs['list']}' not found."
    item_id = await _resolve_item_id(list_id, inputs["item"])
    if item_id is None:
        return f"Item '{inputs['item']}' not found in {inputs['list']}."
    await lists.toggle_list_item(item_id)
    return json.dumps({"ok": True, "toggled": inputs["item"]}, ensure_ascii=False)


async def _remove_item(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Remove an item from a list."""
    list_id = await _resolve_list_id(inputs["list"])
    if list_id is None:
        return f"List '{inputs['list']}' not found."
    item_id = await _resolve_item_id(list_id, inputs["item"])
    if item_id is None:
        return f"Item '{inputs['item']}' not found in {inputs['list']}."
    await lists.delete_list_item(item_id)
    return json.dumps({"ok": True, "removed": inputs["item"]}, ensure_ascii=False)


_LIST = {"type": "string", "description": "List name (case-insensitive)"}
_ITEM = {"type": "string", "description": "Item text"}


def register_lists_tools(registry: ToolRegistry) -> None:
    """Add the generic list tools so the assistant can manage lists in chat."""
    registry.register(Tool(
        name="create_list",
        description="Create a new named list (kind: todo, checklist, shopping, packing).",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "List name"},
                "kind": {"type": "string", "enum": ["todo", "checklist", "shopping", "packing"],
                         "description": "List kind (default todo)"},
            },
            "required": ["name"],
        },
        handler=_create_list,
    ))
    registry.register(Tool(
        name="show_lists",
        description="List all lists with their open-item counts.",
        input_schema={"type": "object", "properties": {}},
        handler=_show_lists,
    ))
    registry.register(Tool(
        name="add_to_list",
        description=("Add an item to a list (creates the list if it does not exist). "
                     "Use for 'add X to my packing list' or a generic todo."),
        input_schema={
            "type": "object",
            "properties": {
                "list": _LIST,
                "item": _ITEM,
                "qty": {"type": "string", "description": "Optional quantity"},
                "due_at": {"type": "string", "description": "Optional 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM'"},
                "kind": {"type": "string", "enum": ["todo", "checklist", "shopping", "packing"],
                         "description": "Kind to use if the list is created now"},
            },
            "required": ["list", "item"],
        },
        handler=_add_item,
    ))
    registry.register(Tool(
        name="show_list",
        description="Read the items of a named list.",
        input_schema={
            "type": "object",
            "properties": {"list": _LIST},
            "required": ["list"],
        },
        handler=_show_list,
    ))
    registry.register(Tool(
        name="check_list_item",
        description="Tick an item off a list (toggles checked).",
        input_schema={
            "type": "object",
            "properties": {"list": _LIST, "item": _ITEM},
            "required": ["list", "item"],
        },
        handler=_check_item,
    ))
    registry.register(Tool(
        name="remove_list_item",
        description="Remove an item from a list.",
        input_schema={
            "type": "object",
            "properties": {"list": _LIST, "item": _ITEM},
            "required": ["list", "item"],
        },
        handler=_remove_item,
    ))
