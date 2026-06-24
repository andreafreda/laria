"""Shopping list — items to buy, with optional quantity, category and price.

Items can be checked off as you shop, and the optional prices roll up into an
estimated basket cost. Name-based lookups use partial, case-insensitive matching
so "milk" finds "Fresh milk 1L".
"""
from __future__ import annotations

from ..db import connect


async def add_shopping_items(items: list[dict]) -> int:
    """Add items to the list (each: name, qty?, category?, price?). Returns count."""
    async with connect() as db:
        for item in items or []:
            await db.execute(
                "INSERT INTO shopping_items (name, qty, category, price) VALUES (?, ?, ?, ?)",
                (item.get("name"), item.get("qty"), item.get("category"), item.get("price")),
            )
        await db.commit()
    return len(items or [])


async def get_shopping_list(include_checked: bool = False) -> list[dict]:
    """The shopping list grouped by category; hides checked-off items by default."""
    query = "SELECT id, name, qty, category, checked, price FROM shopping_items"
    if not include_checked:
        query += " WHERE checked = 0"
    query += " ORDER BY category, name"
    async with connect() as db:
        cur = await db.execute(query)
        rows = await cur.fetchall()
    return [{"id": r[0], "name": r[1], "qty": r[2], "category": r[3],
             "checked": bool(r[4]), "price": r[5]} for r in rows]


async def set_shopping_price(name: str, price: float) -> bool:
    """Set the price of matching items (partial name match). False if none matched."""
    if not (name or "").strip():
        return False
    async with connect() as db:
        cur = await db.execute(
            "UPDATE shopping_items SET price = ? WHERE LOWER(name) LIKE LOWER(?)",
            (price, f"%{name}%"),
        )
        await db.commit()
        return cur.rowcount > 0


async def remove_shopping_item(name: str) -> int:
    """Remove matching items (partial name match). Returns how many were removed."""
    if not (name or "").strip():
        return 0
    async with connect() as db:
        cur = await db.execute(
            "DELETE FROM shopping_items WHERE LOWER(name) LIKE LOWER(?)", (f"%{name}%",)
        )
        await db.commit()
        return cur.rowcount


async def get_shopping_cost(include_checked: bool = True) -> dict:
    """Estimated basket cost from item prices.

    Returns ``{total, priced, missing, count}`` so the UI can show both the sum
    and how complete it is (how many items still lack a price).
    """
    query = "SELECT price FROM shopping_items"
    if not include_checked:
        query += " WHERE checked = 0"
    async with connect() as db:
        cur = await db.execute(query)
        rows = await cur.fetchall()
    prices = [r[0] for r in rows if r[0] is not None]
    total = round(sum(prices), 2)
    return {"total": total, "priced": len(prices),
            "missing": len(rows) - len(prices), "count": len(rows)}


async def check_shopping_item(name: str) -> bool:
    """Tick off matching unchecked items (partial name match) as bought."""
    if not (name or "").strip():
        return False
    async with connect() as db:
        cur = await db.execute(
            "UPDATE shopping_items SET checked = 1 WHERE checked = 0 AND LOWER(name) LIKE LOWER(?)",
            (f"%{name}%",),
        )
        await db.commit()
        return cur.rowcount > 0


async def toggle_shopping_item(item_id: int) -> bool:
    """Flip one item's checked state by id (for tapping a checkbox in the UI)."""
    async with connect() as db:
        cur = await db.execute(
            "UPDATE shopping_items SET checked = 1 - checked WHERE id = ?", (int(item_id),)
        )
        await db.commit()
        return cur.rowcount > 0


async def clear_shopping_list(only_checked: bool = False) -> int:
    """Empty the list — everything, or just the checked-off items. Returns count."""
    async with connect() as db:
        if only_checked:
            cur = await db.execute("DELETE FROM shopping_items WHERE checked = 1")
        else:
            cur = await db.execute("DELETE FROM shopping_items")
        await db.commit()
        return cur.rowcount
