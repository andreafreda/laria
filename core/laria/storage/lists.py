"""Generic household lists: todos, checklists, shopping, packing.

A list has a ``kind`` (todo/checklist/shopping/packing) and holds items. Each
item can carry a quantity, a checked flag, and an optional ``due_at`` date or
time. ``due_at`` is what a later step turns into a scheduled reminder; storage
keeps it as a plain local-time string and stays out of delivery.

The food-specific shopping and pantry lists live under ``storage/food`` and are
left as they are; this module is the general one the UI's Lists page uses.
"""
from __future__ import annotations

from .db import connect

# The kinds a list can have. Free enough for the UI's segment, closed enough that
# a typo does not silently create a fifth bucket.
LIST_KINDS = ("todo", "checklist", "shopping", "packing")


async def create_list(name: str, kind: str = "todo") -> dict:
    """Create an empty list; return its id, name and kind.

    ``kind`` falls back to 'todo' when it is not one of ``LIST_KINDS``.
    """
    if kind not in LIST_KINDS:
        kind = "todo"
    async with connect() as db:
        cur = await db.execute(
            "INSERT INTO lists (name, kind) VALUES (?, ?)", (name, kind)
        )
        await db.commit()
        list_id = cur.lastrowid
    return {"id": list_id, "name": name, "kind": kind}


async def get_lists() -> list[dict]:
    """Every list with its count of open (unchecked) items, newest first.

    Each entry is ``{id, name, kind, open_items}`` so the Lists page can show a
    header and a badge without a second query per list.
    """
    async with connect() as db:
        cur = await db.execute(
            """SELECT l.id, l.name, l.kind,
                      COALESCE(SUM(CASE WHEN i.checked = 0 THEN 1 ELSE 0 END), 0)
               FROM lists l
               LEFT JOIN list_items i ON i.list_id = l.id
               GROUP BY l.id ORDER BY l.id DESC"""
        )
        rows = await cur.fetchall()
    return [{"id": r[0], "name": r[1], "kind": r[2], "open_items": r[3]} for r in rows]


async def delete_list(list_id: int) -> bool:
    """Delete a list and all its items. Returns False if it did not exist."""
    async with connect() as db:
        await db.execute("DELETE FROM list_items WHERE list_id = ?", (int(list_id),))
        cur = await db.execute("DELETE FROM lists WHERE id = ?", (int(list_id),))
        await db.commit()
        return cur.rowcount > 0


async def get_list_items(list_id: int) -> list[dict]:
    """A list's items in display order (unchecked first, then by when added)."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT id, text, qty, checked, due_at FROM list_items
               WHERE list_id = ? ORDER BY checked, id""",
            (int(list_id),),
        )
        rows = await cur.fetchall()
    return [{"id": r[0], "text": r[1], "qty": r[2],
             "checked": bool(r[3]), "due_at": r[4]} for r in rows]


async def add_list_item(list_id: int, text: str, qty: str | None = None,
                        due_at: str | None = None) -> dict:
    """Add one item to a list; return the stored item.

    ``due_at`` is an optional 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM' local-time string;
    wiring it to a reminder is a separate step, here it is just recorded.
    """
    async with connect() as db:
        cur = await db.execute(
            "INSERT INTO list_items (list_id, text, qty, due_at) VALUES (?, ?, ?, ?)",
            (int(list_id), text, qty, due_at),
        )
        await db.commit()
        item_id = cur.lastrowid
    return {"id": item_id, "list_id": int(list_id), "text": text,
            "qty": qty, "checked": False, "due_at": due_at}


async def toggle_list_item(item_id: int) -> bool:
    """Flip one item's checked state by id (for tapping a checkbox in the UI)."""
    async with connect() as db:
        cur = await db.execute(
            "UPDATE list_items SET checked = 1 - checked WHERE id = ?", (int(item_id),)
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_list_item(item_id: int) -> bool:
    """Remove one item by id. Returns False if it did not exist."""
    async with connect() as db:
        cur = await db.execute("DELETE FROM list_items WHERE id = ?", (int(item_id),))
        await db.commit()
        return cur.rowcount > 0
