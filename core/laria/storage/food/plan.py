"""Weekly meal plan — what's intended to be eaten, per day and meal slot.

Distinct from logged meals (``meals.py``): this is the plan ahead, not the
record of what happened. Each slot is keyed by (date, meal_type, member); an
empty member means a shared family plan, a named member is a personal override.
"""
from __future__ import annotations

from ..db import connect


async def set_plan_meal(date: str, meal_type: str, items: str,
                        recipe: str | None = None, servings: int | None = None,
                        kcal: float | None = None, member: str | None = None) -> None:
    """Add or replace a planned meal slot.

    Empty/None ``member`` sets the shared plan for that slot; a member value sets
    that person's personal override. Re-setting the same slot overwrites it.
    """
    member = (member or "").strip().lower()
    async with connect() as db:
        await db.execute(
            """INSERT INTO meal_plan (date, meal_type, member, items, recipe, servings, kcal, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(date, meal_type, member) DO UPDATE SET
                 items=excluded.items, recipe=excluded.recipe,
                 servings=excluded.servings, kcal=excluded.kcal,
                 updated_at=CURRENT_TIMESTAMP""",
            (date, meal_type, member, items, recipe, servings, kcal),
        )
        await db.commit()


async def delete_plan_meal(date: str, meal_type: str, member: str | None = None) -> int:
    """Remove a planned slot (shared if member is empty). Returns rows removed."""
    member = (member or "").strip().lower()
    async with connect() as db:
        cur = await db.execute(
            "DELETE FROM meal_plan WHERE date = ? AND meal_type = ? AND member = ?",
            (date, meal_type, member),
        )
        await db.commit()
        return cur.rowcount


async def get_meal_plan(date_from: str, date_to: str) -> list[dict]:
    """All planned slots in a date range, ordered by day then meal then member."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT date, meal_type, member, items, recipe, servings, kcal FROM meal_plan
               WHERE date >= ? AND date <= ? ORDER BY date, meal_type, member""",
            (date_from, date_to),
        )
        rows = await cur.fetchall()
    return [
        {"date": r[0], "meal_type": r[1], "member": r[2], "items": r[3],
         "recipe": r[4], "servings": r[5], "kcal": r[6]}
        for r in rows
    ]
