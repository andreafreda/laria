"""Home Assistant agenda tools: to-do lists and calendar event editing.

These extend the base HA tools with the task and calendar-management features
ported from HARIA's agenda module. To-do items map to native HA ``todo.*``
lists; calendar editing (delete and update) uses the WebSocket API, since REST
does not expose those operations. Events are addressed by their calendar
entity_id and matched by title within a date window, so the assistant discovers
the calendar with ``get_house_state`` first.

Registered only when Home Assistant is configured, alongside the base tools.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from ...engine.tools import Tool, ToolContext, ToolRegistry
from .client import HaClient
from .tools import _REACHABILITY_ERRORS


def _normalize_event_time(value) -> str | None:
    """Read an event start/end, which HA returns as a dict or an ISO string."""
    if isinstance(value, dict):
        return value.get("dateTime") or value.get("date")
    return value


async def _resolve_todo_list(client: HaClient, name: str | None) -> str | None:
    """Find the todo entity_id to act on: the named one, or the first available."""
    states = await client.get_states(None)
    todo_lists = [
        {"entity_id": s["entity_id"],
         "name": s["attributes"].get("friendly_name", s["entity_id"])}
        for s in states if s["entity_id"].startswith("todo.")
    ]
    if not todo_lists:
        return None
    if not name:
        return todo_lists[0]["entity_id"]
    target = name.strip().lower()
    for entry in todo_lists:
        if entry["entity_id"].lower() == target:
            return entry["entity_id"]
    for entry in todo_lists:
        if target in entry["name"].lower() or target in entry["entity_id"].lower():
            return entry["entity_id"]
    return None


async def _find_events_by_title(client: HaClient, calendar: str, title: str | None,
                                days: int) -> list[dict]:
    """Return events on a calendar whose summary contains ``title`` in a window.

    The window runs from yesterday to ``days`` ahead, so it catches an event
    happening today as well as upcoming ones. Each result keeps the uid (and the
    recurrence id when present), which the WebSocket edit commands require.
    """
    start = datetime.now() - timedelta(days=1)
    end = datetime.now() + timedelta(days=days)
    wanted = (title or "").strip().lower()
    matches = []
    for event in await client.get_calendar_events(
            calendar, start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")):
        summary = (event.get("summary") or "").lower()
        if not wanted or wanted in summary:
            matches.append({
                "uid": event.get("uid"),
                "summary": event.get("summary"),
                "start": event.get("start"),
                "end": event.get("end"),
                "recurrence_id": event.get("recurrence_id"),
            })
    return matches


def register_ha_agenda_tools(registry: ToolRegistry, client: HaClient) -> None:
    """Add the HA to-do and calendar-editing tools, bound to a live client."""

    async def list_todo_lists(inputs: dict[str, Any], ctx: ToolContext) -> str:
        """List the available Home Assistant to-do lists (todo.* entities)."""
        try:
            states = await client.get_states(None)
        except _REACHABILITY_ERRORS as error:
            return f"Home Assistant error: {error}"
        lists = [
            {"entity_id": s["entity_id"],
             "name": s["attributes"].get("friendly_name", s["entity_id"])}
            for s in states if s["entity_id"].startswith("todo.")
        ]
        return json.dumps(lists, ensure_ascii=False) if lists else "No to-do lists in Home Assistant."

    async def add_task(inputs: dict[str, Any], ctx: ToolContext) -> str:
        """Add an item to a to-do list, with an optional due date and notes."""
        try:
            list_id = await _resolve_todo_list(client, inputs.get("list"))
            if not list_id:
                return f"List '{inputs.get('list')}' not found. Use list_todo_lists."
            data = {"entity_id": list_id, "item": inputs["item"]}
            if inputs.get("description"):
                data["description"] = inputs["description"]
            if inputs.get("due_datetime"):
                data["due_datetime"] = inputs["due_datetime"]
            elif inputs.get("due_date"):
                data["due_date"] = inputs["due_date"]
            await client.call_service("todo", "add_item", data)
        except _REACHABILITY_ERRORS as error:
            return f"Home Assistant error: {error}"
        return json.dumps({"ok": True, "added": inputs["item"], "list": list_id}, ensure_ascii=False)

    async def get_tasks(inputs: dict[str, Any], ctx: ToolContext) -> str:
        """Read a to-do list's items, optionally filtered by status."""
        try:
            list_id = await _resolve_todo_list(client, inputs.get("list"))
            if not list_id:
                return f"List '{inputs.get('list')}' not found. Use list_todo_lists."
            data = {"entity_id": list_id}
            if inputs.get("status"):
                data["status"] = inputs["status"]
            response = await client.call_service("todo", "get_items", data, return_response=True)
        except _REACHABILITY_ERRORS as error:
            return f"Home Assistant error: {error}"
        service_response = response.get("service_response", {}) if isinstance(response, dict) else {}
        items = service_response.get(list_id, {}).get("items", [])
        return json.dumps({"list": list_id, "items": items}, ensure_ascii=False)

    async def complete_task(inputs: dict[str, Any], ctx: ToolContext) -> str:
        """Mark a to-do item as completed."""
        try:
            list_id = await _resolve_todo_list(client, inputs.get("list"))
            if not list_id:
                return f"List '{inputs.get('list')}' not found. Use list_todo_lists."
            await client.call_service("todo", "update_item",
                                      {"entity_id": list_id, "item": inputs["item"], "status": "completed"})
        except _REACHABILITY_ERRORS as error:
            return f"Home Assistant error: {error}"
        return json.dumps({"ok": True, "completed": inputs["item"], "list": list_id}, ensure_ascii=False)

    async def remove_task(inputs: dict[str, Any], ctx: ToolContext) -> str:
        """Remove an item from a to-do list."""
        try:
            list_id = await _resolve_todo_list(client, inputs.get("list"))
            if not list_id:
                return f"List '{inputs.get('list')}' not found. Use list_todo_lists."
            await client.call_service("todo", "remove_item", {"entity_id": list_id, "item": inputs["item"]})
        except _REACHABILITY_ERRORS as error:
            return f"Home Assistant error: {error}"
        return json.dumps({"ok": True, "removed": inputs["item"], "list": list_id}, ensure_ascii=False)

    async def update_task(inputs: dict[str, Any], ctx: ToolContext) -> str:
        """Edit a to-do item: rename, change due date, notes, or status."""
        try:
            list_id = await _resolve_todo_list(client, inputs.get("list"))
            if not list_id:
                return f"List '{inputs.get('list')}' not found. Use list_todo_lists."
            data = {"entity_id": list_id, "item": inputs["item"]}
            if inputs.get("new_item"):
                data["rename"] = inputs["new_item"]
            if inputs.get("status"):
                data["status"] = inputs["status"]
            if inputs.get("description") is not None:
                data["description"] = inputs["description"]
            if inputs.get("due_datetime"):
                data["due_datetime"] = inputs["due_datetime"]
            elif inputs.get("due_date"):
                data["due_date"] = inputs["due_date"]
            if len(data) <= 2:
                return "Nothing to update: provide new_item, status, description, or a due date."
            await client.call_service("todo", "update_item", data)
        except _REACHABILITY_ERRORS as error:
            return f"Home Assistant error: {error}"
        return json.dumps({"ok": True, "updated": inputs["item"], "list": list_id}, ensure_ascii=False)

    async def delete_calendar_event(inputs: dict[str, Any], ctx: ToolContext) -> str:
        """Delete calendar events matching a title within a date window."""
        try:
            matches = await _find_events_by_title(
                client, inputs["calendar"], inputs.get("title"), int(inputs.get("days") or 60))
            if not matches:
                return json.dumps({"ok": False, "deleted": 0, "msg": "No matching event"}, ensure_ascii=False)
            for event in matches:
                payload = {"type": "calendar/event/delete",
                           "entity_id": inputs["calendar"], "uid": event["uid"]}
                if event.get("recurrence_id"):
                    payload["recurrence_id"] = event["recurrence_id"]
                    payload["recurrence_range"] = "THISANDFUTURE"
                await client.ws_command(payload)
        except _REACHABILITY_ERRORS as error:
            return f"Home Assistant error: {error}"
        return json.dumps({"ok": True, "deleted": len(matches)}, ensure_ascii=False)

    async def update_calendar_event(inputs: dict[str, Any], ctx: ToolContext) -> str:
        """Update calendar events matching a title with the supplied new fields.

        HA requires the full event on update, so fields the caller omits are
        filled in from the existing event.
        """
        new_fields = _build_event_update(inputs)
        if not new_fields:
            return "Nothing to update: provide new_title, start+end, description, or location."
        try:
            matches = await _find_events_by_title(
                client, inputs["calendar"], inputs.get("title"), int(inputs.get("days") or 60))
            if not matches:
                return json.dumps({"ok": False, "updated": 0, "msg": "No matching event"}, ensure_ascii=False)
            for event in matches:
                merged = dict(new_fields)
                if "summary" not in merged:
                    merged["summary"] = event.get("summary")
                if "dtstart" not in merged:
                    merged["dtstart"] = _normalize_event_time(event.get("start"))
                    merged["dtend"] = _normalize_event_time(event.get("end"))
                payload = {"type": "calendar/event/update", "entity_id": inputs["calendar"],
                           "uid": event["uid"], "event": merged}
                if event.get("recurrence_id"):
                    payload["recurrence_id"] = event["recurrence_id"]
                    payload["recurrence_range"] = "THISANDFUTURE"
                await client.ws_command(payload)
        except _REACHABILITY_ERRORS as error:
            return f"Home Assistant error: {error}"
        return json.dumps({"ok": True, "updated": len(matches)}, ensure_ascii=False)

    _register_todo_tools(registry, list_todo_lists, add_task, get_tasks,
                         complete_task, remove_task, update_task)
    _register_calendar_edit_tools(registry, delete_calendar_event, update_calendar_event)


def _build_event_update(inputs: dict[str, Any]) -> dict[str, Any]:
    """Collect the calendar fields the caller wants to change into HA's shape."""
    fields: dict[str, Any] = {}
    if inputs.get("new_title"):
        fields["summary"] = inputs["new_title"]
    if inputs.get("description") is not None:
        fields["description"] = inputs["description"]
    if inputs.get("location") is not None:
        fields["location"] = inputs["location"]
    if inputs.get("start") and inputs.get("end"):
        fields["dtstart"] = inputs["start"]
        fields["dtend"] = inputs["end"]
    elif inputs.get("start_date") and inputs.get("end_date"):
        fields["dtstart"] = inputs["start_date"]
        fields["dtend"] = inputs["end_date"]
    return fields


_LIST = {"type": "string", "description": "List name or entity_id; default is the first list"}
_ITEM = {"type": "string", "description": "Exact item name"}


def _register_todo_tools(registry, list_todo_lists, add_task, get_tasks,
                         complete_task, remove_task, update_task) -> None:
    """Register the six to-do tools (kept here so the handler closures stay above)."""
    registry.register(Tool(
        name="list_todo_lists",
        description="List the Home Assistant to-do lists (todo.* entities).",
        input_schema={"type": "object", "properties": {}},
        handler=list_todo_lists,
    ))
    registry.register(Tool(
        name="add_task",
        description="Add an item to a Home Assistant to-do list (e.g. add milk to the shopping list).",
        input_schema={
            "type": "object",
            "properties": {
                "item": {"type": "string", "description": "What to do"},
                "list": _LIST,
                "due_date": {"type": "string", "description": "Due date 'YYYY-MM-DD'"},
                "due_datetime": {"type": "string", "description": "Due ISO 'YYYY-MM-DDTHH:MM:SS'"},
                "description": {"type": "string", "description": "Notes"},
            },
            "required": ["item"],
        },
        handler=add_task,
    ))
    registry.register(Tool(
        name="get_tasks",
        description="Read items of a Home Assistant to-do list (default the first list).",
        input_schema={
            "type": "object",
            "properties": {
                "list": _LIST,
                "status": {"type": "string", "enum": ["needs_action", "completed"],
                           "description": "Filter by status (default all)"},
            },
        },
        handler=get_tasks,
    ))
    registry.register(Tool(
        name="complete_task",
        description="Mark an item completed in a Home Assistant to-do list.",
        input_schema={
            "type": "object",
            "properties": {"item": _ITEM, "list": _LIST},
            "required": ["item"],
        },
        handler=complete_task,
    ))
    registry.register(Tool(
        name="remove_task",
        description="Remove an item from a Home Assistant to-do list.",
        input_schema={
            "type": "object",
            "properties": {"item": _ITEM, "list": _LIST},
            "required": ["item"],
        },
        handler=remove_task,
    ))
    registry.register(Tool(
        name="update_task",
        description=("Edit an item in a Home Assistant to-do list: rename (new_item), due date, "
                     "notes, or status."),
        input_schema={
            "type": "object",
            "properties": {
                "item": _ITEM,
                "list": _LIST,
                "new_item": {"type": "string", "description": "New name"},
                "due_date": {"type": "string", "description": "Due date 'YYYY-MM-DD'"},
                "due_datetime": {"type": "string", "description": "Due ISO datetime"},
                "description": {"type": "string", "description": "Notes"},
                "status": {"type": "string", "enum": ["needs_action", "completed"], "description": "Status"},
            },
            "required": ["item"],
        },
        handler=update_task,
    ))


def _register_calendar_edit_tools(registry, delete_calendar_event, update_calendar_event) -> None:
    """Register the calendar delete and update tools."""
    registry.register(Tool(
        name="delete_calendar_event",
        description=("Delete events from a Home Assistant calendar matching a title, within a date "
                     "window (default 60 days ahead). Find the calendar with get_house_state."),
        input_schema={
            "type": "object",
            "properties": {
                "calendar": {"type": "string", "description": "Calendar entity_id (e.g. calendar.family)"},
                "title": {"type": "string", "description": "Event name or part of it"},
                "days": {"type": "integer", "description": "Search window ahead in days (default 60)"},
            },
            "required": ["calendar", "title"],
        },
        handler=delete_calendar_event,
    ))
    registry.register(Tool(
        name="update_calendar_event",
        description=("Update events on a Home Assistant calendar matching a title. Apply new_title, "
                     "start+end (ISO) or start_date+end_date, description, or location."),
        input_schema={
            "type": "object",
            "properties": {
                "calendar": {"type": "string", "description": "Calendar entity_id"},
                "title": {"type": "string", "description": "Event name or part of it"},
                "new_title": {"type": "string", "description": "New title"},
                "start": {"type": "string", "description": "New start ISO 'YYYY-MM-DDTHH:MM:SS'"},
                "end": {"type": "string", "description": "New end ISO"},
                "start_date": {"type": "string", "description": "New all-day start 'YYYY-MM-DD'"},
                "end_date": {"type": "string", "description": "New all-day end 'YYYY-MM-DD'"},
                "description": {"type": "string", "description": "New notes"},
                "location": {"type": "string", "description": "New location"},
                "days": {"type": "integer", "description": "Search window ahead in days (default 60)"},
            },
            "required": ["calendar", "title"],
        },
        handler=update_calendar_event,
    ))
