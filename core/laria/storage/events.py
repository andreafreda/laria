"""Recurring calendar events: birthdays, anniversaries, and the like.

Each event repeats yearly on a month and day (so no year is stored), belongs to
the user who created it, and can announce itself a few days early. The daily
event job reads the active events and decides which fire today; the date logic
lives in ``laria.modules.events`` so it stays pure and testable.
"""
from __future__ import annotations

from .db import connect

# The kinds the assistant understands. 'custom' covers anything else.
EVENT_KINDS = ("birthday", "anniversary", "nameday", "custom")


def _event_row(row) -> dict:
    return {"id": row[0], "user_id": row[1], "label": row[2], "kind": row[3],
            "month": row[4], "day": row[5], "notify_days_before": row[6]}


async def add_event(user_id: str, label: str, kind: str, month: int, day: int,
                    notify_days_before: int = 0) -> dict:
    """Create a yearly event; return the stored row.

    ``kind`` falls back to 'custom' when it is not a known kind. Month and day
    are the recurring date (1-12, 1-31); the caller validates the calendar.
    """
    if kind not in EVENT_KINDS:
        kind = "custom"
    async with connect() as db:
        cur = await db.execute(
            """INSERT INTO events (user_id, label, kind, month, day, notify_days_before)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, label, kind, int(month), int(day), int(notify_days_before)),
        )
        await db.commit()
        event_id = cur.lastrowid
    return {"id": event_id, "user_id": user_id, "label": label, "kind": kind,
            "month": int(month), "day": int(day),
            "notify_days_before": int(notify_days_before)}


async def get_user_events(user_id: str) -> list[dict]:
    """A user's active events, ordered by month and day."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT id, user_id, label, kind, month, day, notify_days_before
               FROM events WHERE active = 1 AND user_id = ?
               ORDER BY month, day""",
            (user_id,),
        )
        return [_event_row(r) for r in await cur.fetchall()]


async def get_active_events() -> list[dict]:
    """Every active event across users (for the daily notification job)."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT id, user_id, label, kind, month, day, notify_days_before
               FROM events WHERE active = 1"""
        )
        return [_event_row(r) for r in await cur.fetchall()]


async def delete_event(event_id: int, user_id: str | None = None) -> bool:
    """Deactivate an event. Scoped to a user when ``user_id`` is given."""
    where = "id = ?"
    params: list = [int(event_id)]
    if user_id is not None:
        where += " AND user_id = ?"
        params.append(user_id)
    async with connect() as db:
        cur = await db.execute(f"UPDATE events SET active = 0 WHERE {where}", params)
        await db.commit()
        return cur.rowcount > 0
