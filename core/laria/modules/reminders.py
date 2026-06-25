"""Reminder tools: timed pings the assistant sends back to the user.

A reminder is either one-shot (``remind_at``, an ISO datetime) or recurring
(``recurring``, a 5-field cron). The scheduler fires it and the notifier delivers
it; this module only manages the records and keeps the scheduler in sync. Stored
under the calling user's id, so each user sees and edits only their own.
"""
from __future__ import annotations

from datetime import datetime
import json

from ..engine.tools import Tool, ToolContext, ToolRegistry
from ..scheduler import Scheduler
from ..storage import misc


def _is_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


def register_reminders_tools(registry: ToolRegistry,
                             scheduler: Scheduler | None = None) -> None:
    """Add reminder tools to the registry.

    ``scheduler`` is optional: with it, reminders fire live; without it (a
    web-only process) they are stored and scheduled when a scheduler next loads
    active reminders.
    """

    async def _set_reminder(inputs: dict, ctx: ToolContext) -> str:
        remind_at = inputs.get("remind_at") or None
        recurring = inputs.get("recurring") or None
        if not remind_at and not recurring:
            return "Provide remind_at (one-shot) or recurring (cron)."
        if remind_at and not _is_iso_datetime(remind_at):
            return "remind_at must be an ISO datetime (YYYY-MM-DDTHH:MM:SS)."
        reminder = await misc.add_reminder(ctx.user_id, inputs["message"], remind_at, recurring)
        if scheduler is not None and not scheduler.schedule_reminder(reminder):
            await misc.deactivate_reminder(reminder["id"], ctx.user_id)
            return "That time is invalid or in the past."
        return f"Reminder #{reminder['id']} created."

    async def _list_reminders(inputs: dict, ctx: ToolContext) -> str:
        reminders = await misc.get_user_reminders(ctx.user_id)
        return json.dumps(reminders, ensure_ascii=False) if reminders else "No active reminders."

    async def _cancel_reminder(inputs: dict, ctx: ToolContext) -> str:
        cancelled = await misc.deactivate_reminder(int(inputs["id"]), ctx.user_id)
        if not cancelled:
            return f"Reminder #{inputs['id']} not found."
        if scheduler is not None:
            scheduler.cancel_reminder(int(inputs["id"]))
        return f"Reminder #{inputs['id']} cancelled."

    async def _update_reminder(inputs: dict, ctx: ToolContext) -> str:
        reminder_id = int(inputs["id"])
        if inputs.get("remind_at") and not _is_iso_datetime(inputs["remind_at"]):
            return "remind_at must be an ISO datetime (YYYY-MM-DDTHH:MM:SS)."
        reminder = await misc.update_reminder(
            reminder_id, ctx.user_id,
            message=inputs.get("message"),
            remind_at=inputs.get("remind_at"),
            recurring=inputs.get("recurring"),
        )
        if not reminder:
            return f"Reminder #{reminder_id} not found or nothing to change."
        time_changed = inputs.get("remind_at") is not None or inputs.get("recurring") is not None
        if time_changed and scheduler is not None:
            scheduler.cancel_reminder(reminder_id)
            if not scheduler.schedule_reminder(reminder):
                await misc.deactivate_reminder(reminder_id, ctx.user_id)
                return "The new time is invalid or in the past."
        return f"Reminder #{reminder_id} updated."

    registry.register(Tool(
        name="set_reminder",
        description=("Create a reminder that pings the user at a time. Use remind_at (ISO datetime) "
                     "for one-shot, or recurring (5-field cron) for repeating. Convert the user's "
                     "requested time accordingly."),
        input_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Reminder text"},
                "remind_at": {"type": "string", "description": "ISO datetime for a one-shot reminder"},
                "recurring": {"type": "string", "description": "5-field cron for a repeating reminder"},
            },
            "required": ["message"],
        },
        handler=_set_reminder,
    ))
    registry.register(Tool(
        name="list_reminders",
        description="List the current user's active reminders.",
        input_schema={"type": "object", "properties": {}},
        handler=_list_reminders,
    ))
    registry.register(Tool(
        name="cancel_reminder",
        description="Cancel a reminder by id (from list_reminders).",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "Reminder id"}},
            "required": ["id"],
        },
        handler=_cancel_reminder,
    ))
    registry.register(Tool(
        name="update_reminder",
        description=("Edit a reminder by id. Pass the fields to change: message, remind_at "
                     "(ISO datetime one-shot) or recurring (cron). Changing the time reschedules it."),
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Reminder id"},
                "message": {"type": "string", "description": "New text"},
                "remind_at": {"type": "string", "description": "New ISO datetime one-shot"},
                "recurring": {"type": "string", "description": "New 5-field cron (empty clears recurrence)"},
            },
            "required": ["id"],
        },
        handler=_update_reminder,
    ))
