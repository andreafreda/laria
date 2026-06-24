"""Hydration log — how much each member drank, in millilitres.

A tiny append log behind "add a glass" buttons and a daily total. The undo
helper exists because the common mistake is one tap too many.
"""
from __future__ import annotations

from ..db import connect


async def add_hydration(member: str, ml: float) -> dict:
    """Log a drink for a member (in ml); return the stored entry."""
    async with connect() as db:
        cur = await db.execute(
            "INSERT INTO hydration_log (member, ml) VALUES (?, ?)", (member, ml)
        )
        await db.commit()
        entry_id = cur.lastrowid
    return {"id": entry_id, "member": member, "ml": ml}


async def delete_last_hydration(member: str) -> bool:
    """Undo a member's most recent drink logged today. False if nothing today."""
    async with connect() as db:
        last_today = await (await db.execute(
            """SELECT id FROM hydration_log
               WHERE member = ? AND DATE(logged_at) = DATE('now', 'localtime')
               ORDER BY logged_at DESC LIMIT 1""",
            (member,),
        )).fetchone()
        if not last_today:
            return False
        cur = await db.execute("DELETE FROM hydration_log WHERE id = ?", (last_today[0],))
        await db.commit()
        return cur.rowcount > 0


async def get_hydration_day(member: str, day: str) -> dict:
    """A member's total ml and number of drinks on a given day."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT COALESCE(SUM(ml),0), COUNT(*) FROM hydration_log
               WHERE member = ? AND DATE(logged_at) = ?""",
            (member, day),
        )
        total_ml, count = await cur.fetchone()
    return {"ml_total": round(total_ml, 1), "count": count}
