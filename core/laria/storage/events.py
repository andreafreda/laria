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

_COLUMNS = "id, user_id, label, kind, month, day, notify_offsets"


def _parse_offsets(raw: str) -> list[int]:
    """Read the stored CSV of day-offsets into a sorted, de-duplicated list.

    An empty or malformed value falls back to [0] (notify on the day only), so a
    row always has at least one notification day.
    """
    offsets = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            offsets.add(int(part))
    return sorted(offsets) if offsets else [0]


def _format_offsets(offsets) -> str:
    """Serialize offsets to the stored CSV, normalized (sorted, unique, >=0)."""
    clean = sorted({int(o) for o in offsets if int(o) >= 0}) or [0]
    return ",".join(str(o) for o in clean)


def _event_row(row) -> dict:
    return {"id": row[0], "user_id": row[1], "label": row[2], "kind": row[3],
            "month": row[4], "day": row[5], "notify_offsets": _parse_offsets(row[6])}


async def add_event(user_id: str, label: str, kind: str, month: int, day: int,
                    notify_offsets=None) -> dict:
    """Create a yearly event; return the stored row.

    ``kind`` falls back to 'custom' when unknown. ``notify_offsets`` is the list
    of day-offsets to announce on (e.g. [30, 7, 1, 0] = a month, a week, a day
    before, and on the day); it defaults to [0] (the day itself). Month and day
    are the recurring date (1-12, 1-31); the caller validates the calendar.
    """
    if kind not in EVENT_KINDS:
        kind = "custom"
    offsets_csv = _format_offsets(notify_offsets if notify_offsets is not None else [0])
    async with connect() as db:
        cur = await db.execute(
            """INSERT INTO events (user_id, label, kind, month, day, notify_offsets)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, label, kind, int(month), int(day), offsets_csv),
        )
        await db.commit()
        event_id = cur.lastrowid
    return {"id": event_id, "user_id": user_id, "label": label, "kind": kind,
            "month": int(month), "day": int(day), "notify_offsets": _parse_offsets(offsets_csv)}


async def get_user_events(user_id: str) -> list[dict]:
    """A user's active events, ordered by month and day."""
    async with connect() as db:
        cur = await db.execute(
            f"""SELECT {_COLUMNS} FROM events WHERE active = 1 AND user_id = ?
                ORDER BY month, day""",
            (user_id,),
        )
        return [_event_row(r) for r in await cur.fetchall()]


async def get_active_events() -> list[dict]:
    """Every active event across users (for the daily notification job)."""
    async with connect() as db:
        cur = await db.execute(f"SELECT {_COLUMNS} FROM events WHERE active = 1")
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
