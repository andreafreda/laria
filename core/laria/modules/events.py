"""Recurring event tools and the "is it due today" date logic.

The assistant can add, list, and remove yearly events (birthdays, anniversaries,
custom). The date helpers here are pure so the daily notification job and the
tests can reason about "which events fire today" without a database or a clock.
"""
from __future__ import annotations

import json
from datetime import date

from ..engine.tools import Tool, ToolContext, ToolRegistry
from ..storage import events

_KIND_ICON = {"birthday": "🎂", "anniversary": "💍", "nameday": "📛", "custom": "📅"}


def next_occurrence(month: int, day: int, today: date) -> date:
    """The next date this recurring day falls on, today or later.

    Feb 29 in a non-leap year is observed on Feb 28 so it never disappears.
    """
    for year in (today.year, today.year + 1):
        occurrence = _safe_date(year, month, day)
        if occurrence >= today:
            return occurrence
    return _safe_date(today.year + 1, month, day)


def _safe_date(year: int, month: int, day: int) -> date:
    try:
        return date(year, month, day)
    except ValueError:
        return date(year, month, 28) if month == 2 else date(year, month, 1)


def days_until(event: dict, today: date) -> int:
    """Whole days from ``today`` to the event's next occurrence (0 = today)."""
    return (next_occurrence(event["month"], event["day"], today) - today).days


def _offsets(event: dict) -> list[int]:
    return event.get("notify_offsets") or [0]


def is_due(event: dict, today: date) -> bool:
    """True when today is exactly one of the event's configured lead days.

    Offsets are discrete (e.g. [30, 7, 1, 0]): the event announces a month
    before, a week before, the day before, and on the day, and stays silent on
    the days in between.
    """
    return days_until(event, today) in _offsets(event)


def _lead_phrase(remaining: int) -> str:
    if remaining == 0:
        return "today"
    if remaining == 1:
        return "tomorrow"
    if remaining == 7:
        return "in a week"
    if remaining in (30, 31):
        return "in a month"
    return f"in {remaining} days"


def event_message(event: dict, today: date) -> str:
    """The notification line for a due event, phrased by how far off it is."""
    icon = _KIND_ICON.get(event["kind"], "📅")
    return f"{icon} {event['label']} — {_lead_phrase(days_until(event, today))}"


def register_events_tools(registry: ToolRegistry) -> None:
    """Add the recurring-event tools so the assistant can manage them in chat."""

    async def _add_event(inputs: dict, ctx: ToolContext) -> str:
        event = await events.add_event(
            ctx.user_id, inputs["label"], inputs.get("kind", "custom"),
            int(inputs["month"]), int(inputs["day"]),
            inputs.get("notify_offsets") or [0])
        return json.dumps({"ok": True, "event": event}, ensure_ascii=False)

    async def _list_events(inputs: dict, ctx: ToolContext) -> str:
        items = await events.get_user_events(ctx.user_id)
        return json.dumps(items, ensure_ascii=False) if items else "No events yet."

    async def _delete_event(inputs: dict, ctx: ToolContext) -> str:
        deleted = await events.delete_event(int(inputs["id"]), ctx.user_id)
        return json.dumps({"ok": deleted, "id": inputs["id"]}, ensure_ascii=False)

    registry.register(Tool(
        name="add_event",
        description=("Add a yearly recurring event (birthday, anniversary, nameday, custom). "
                     "Convert the user's date to month (1-12) and day (1-31). "
                     "notify_offsets is the list of days-before to announce on: "
                     "0=on the day, 1=day before, 7=a week before, 30=a month before. "
                     "Include every lead time the user asks for, e.g. [30,7,1,0]."),
        input_schema={
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "What it is, e.g. 'Marina's birthday'"},
                "kind": {"type": "string", "enum": list(events.EVENT_KINDS),
                         "description": "Event kind (default custom)"},
                "month": {"type": "integer", "description": "Month 1-12"},
                "day": {"type": "integer", "description": "Day 1-31"},
                "notify_offsets": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Days-before to notify (e.g. [30,7,2,1,0]). Default [0].",
                },
            },
            "required": ["label", "month", "day"],
        },
        handler=_add_event,
    ))
    registry.register(Tool(
        name="list_events",
        description="List the current user's recurring events (birthdays, anniversaries, ...).",
        input_schema={"type": "object", "properties": {}},
        handler=_list_events,
    ))
    registry.register(Tool(
        name="delete_event",
        description="Delete a recurring event by id (from list_events).",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
        handler=_delete_event,
    ))
