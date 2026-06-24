"""Pantry, what's currently in stock at home, with optional expiry dates.

Tracks staples so the assistant can warn about items about to expire and answer
"do we have…". Name lookups are partial/case-insensitive, except consuming a
item, which matches the exact name so you don't remove the wrong thing.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..db import build_set_clause, connect


async def add_pantry_items(items: list[dict]) -> int:
    """Add stock items (each: name, qty?, category?, expires_on?). Returns count.

    Items without a name are skipped, so a loose list won't insert blank rows.
    """
    added = 0
    async with connect() as db:
        for item in items:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            await db.execute(
                """INSERT INTO pantry_items (name, qty, category, expires_on, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (name, item.get("qty"), item.get("category"), item.get("expires_on")),
            )
            added += 1
        await db.commit()
    return added


async def get_pantry(category: str | None = None) -> list[dict]:
    """Pantry contents, optionally one category, soonest-to-expire first."""
    query = "SELECT id, name, qty, category, expires_on FROM pantry_items"
    params: list = []
    if category:
        query += " WHERE category = ?"; params.append(category)
    query += " ORDER BY (expires_on IS NULL), expires_on, name"
    async with connect() as db:
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
    return [{"id": r[0], "name": r[1], "qty": r[2], "category": r[3], "expires_on": r[4]}
            for r in rows]


async def get_pantry_expiring(within_days: int = 3) -> list[dict]:
    """Items expiring within N days (or already expired), for "use it up" nudges."""
    cutoff = (date.today() + timedelta(days=within_days)).isoformat()
    async with connect() as db:
        cur = await db.execute(
            """SELECT id, name, qty, category, expires_on FROM pantry_items
               WHERE expires_on IS NOT NULL AND expires_on <= ?
               ORDER BY expires_on""",
            (cutoff,),
        )
        rows = await cur.fetchall()
    return [{"id": r[0], "name": r[1], "qty": r[2], "category": r[3], "expires_on": r[4]}
            for r in rows]


async def consume_pantry_item(name: str) -> int:
    """Remove a stock item by its exact (case-insensitive) name. Returns count.

    Exact match on purpose: "used the milk" shouldn't also clear "milk chocolate".
    """
    async with connect() as db:
        cur = await db.execute(
            "DELETE FROM pantry_items WHERE LOWER(name) = ?", ((name or "").strip().lower(),)
        )
        await db.commit()
        return cur.rowcount


async def update_pantry_item(name: str, qty: str | None = None,
                             category: str | None = None,
                             expires_on: str | None = None) -> int:
    """Edit matching stock items (partial name match), changing only fields passed.

    Returns how many rows changed (0 if the name is blank or nothing matched).
    """
    changes = {
        "qty": qty,
        "category": category,
        "expires_on": (expires_on or None) if expires_on is not None else None,
    }
    clause, params = build_set_clause(changes)
    if not clause or not (name or "").strip():
        return 0
    clause += ", updated_at = CURRENT_TIMESTAMP"
    params.append(f"%{name}%")
    async with connect() as db:
        cur = await db.execute(
            f"UPDATE pantry_items SET {clause} WHERE LOWER(name) LIKE LOWER(?)", params
        )
        await db.commit()
        return cur.rowcount


async def clear_pantry() -> int:
    """Empty the pantry entirely. Returns how many items were removed."""
    async with connect() as db:
        cur = await db.execute("DELETE FROM pantry_items")
        await db.commit()
        return cur.rowcount
