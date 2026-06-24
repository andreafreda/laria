"""Weight log — timestamped weight (and BMI) measurements per member.

A simple append-only log; ``get_weight_stats`` turns it into the trend numbers a
dashboard shows (latest, min, max, change over a window).
"""
from __future__ import annotations

from datetime import date, timedelta

from ..db import connect


async def add_weight(member: str, weight_kg: float, bmi: float | None) -> dict:
    """Record a weight measurement for a member; return the stored entry."""
    async with connect() as db:
        cur = await db.execute(
            "INSERT INTO weight_log (member, weight_kg, bmi) VALUES (?, ?, ?)",
            (member, weight_kg, bmi),
        )
        await db.commit()
        weight_id = cur.lastrowid
    return {"id": weight_id, "member": member, "weight_kg": weight_kg, "bmi": bmi}


async def get_weight_history(member: str, limit: int = 20) -> list[dict]:
    """A member's most recent weight entries, newest first."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT id, weight_kg, bmi, logged_at FROM weight_log
               WHERE member = ? ORDER BY logged_at DESC LIMIT ?""",
            (member, limit),
        )
        rows = await cur.fetchall()
    return [{"id": i, "weight_kg": w, "bmi": b, "logged_at": t} for i, w, b, t in rows]


async def update_weight(weight_id: int, weight_kg: float | None = None,
                        bmi: float | None = None) -> bool:
    """Correct a logged measurement by id. Returns False if nothing changed."""
    assignments: list[str] = []
    values: list = []
    if weight_kg is not None:
        assignments.append("weight_kg = ?"); values.append(weight_kg)
    if bmi is not None:
        assignments.append("bmi = ?"); values.append(bmi)
    if not assignments:
        return False
    values.append(int(weight_id))
    async with connect() as db:
        cur = await db.execute(
            f"UPDATE weight_log SET {', '.join(assignments)} WHERE id = ?", values
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_weight(weight_id: int) -> bool:
    """Delete a logged measurement by id. Returns False if there was none."""
    async with connect() as db:
        cur = await db.execute("DELETE FROM weight_log WHERE id = ?", (int(weight_id),))
        await db.commit()
        return cur.rowcount > 0


async def get_weight_stats(member: str, days: int = 30) -> dict | None:
    """Trend summary over the last ``days``: latest, min, max, delta, count.

    ``delta`` is latest minus the first measurement in the window. If the window
    is empty it falls back to the single most recent measurement ever; if the
    member has never logged a weight, returns None.
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    async with connect() as db:
        cur = await db.execute(
            """SELECT weight_kg, bmi, logged_at FROM weight_log
               WHERE member = ? AND logged_at >= ?
               ORDER BY logged_at ASC""",
            (member, since),
        )
        rows = await cur.fetchall()

    if not rows:
        return await _latest_only(member, days)

    weights = [r[0] for r in rows]
    first_weight = weights[0]
    last_weight, last_bmi, last_at = rows[-1]
    return {
        "latest": last_weight, "latest_bmi": last_bmi, "latest_at": last_at,
        "min": min(weights), "max": max(weights),
        "delta": round(last_weight - first_weight, 1), "count": len(rows), "days": days,
    }


async def _latest_only(member: str, days: int) -> dict | None:
    """Stats fallback when the window has no entries: the single latest weight.

    Reported as a flat trend (min=max=latest, delta=0) so callers get the same
    shape as a normal window. None if the member has never logged a weight.
    """
    async with connect() as db:
        cur = await db.execute(
            """SELECT weight_kg, bmi, logged_at FROM weight_log
               WHERE member = ? ORDER BY logged_at DESC LIMIT 1""",
            (member,),
        )
        last = await cur.fetchone()
    if not last:
        return None
    weight, bmi, logged_at = last
    return {"latest": weight, "latest_bmi": bmi, "latest_at": logged_at,
            "min": weight, "max": weight, "delta": 0.0, "count": 1, "days": days}
