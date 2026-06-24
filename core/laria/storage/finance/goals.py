"""Savings goals, a target amount, optionally by a deadline, and progress toward it.

Think of each goal as a labelled piggy bank: it has a target, a running saved
amount, and (optionally) a target date. ``get_goals`` derives the helpful bits:
how much is left and how much to set aside per month to get there in time.
"""
from __future__ import annotations

from datetime import date

from ..db import connect


def _months_until(target_date: str, today: date) -> int:
    """Whole months from today until ``target_date`` (0 if it's today or past).

    A partial final month counts only if today's day-of-month has passed the
    target's, so "3 months left" never over-promises time. Returns 0 on an
    unparseable date so callers treat it as "no deadline guidance".
    """
    try:
        deadline = date.fromisoformat(target_date)
    except (ValueError, TypeError):
        return 0
    if deadline <= today:
        return 0
    months = (deadline.year - today.year) * 12 + (deadline.month - today.month)
    if deadline.day < today.day:
        months -= 1
    return max(months, 1)


async def set_goal(name: str, target: float, target_date: str | None = None) -> int:
    """Create a goal or update its target/deadline; return its id.

    The already-saved amount is left untouched, change that with
    ``add_to_goal``. The target is stored as a positive number.
    """
    name = (name or "").strip()
    async with connect() as conn:
        await conn.execute(
            """INSERT INTO finance_goals (name, target, target_date)
               VALUES (?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                   target=excluded.target, target_date=excluded.target_date""",
            (name, abs(float(target)), target_date or None),
        )
        await conn.commit()
        cur = await conn.execute("SELECT id FROM finance_goals WHERE name=?", (name,))
        return (await cur.fetchone())[0]


async def add_to_goal(name: str, amount: float) -> dict | None:
    """Add to (or, with a negative amount, withdraw from) a goal's saved total.

    The saved amount never drops below zero. Returns the goal's new state
    (``{name, saved, target, reached}``) or None if there's no such goal.
    """
    async with connect() as conn:
        cur = await conn.execute(
            """UPDATE finance_goals
               SET saved = max(0, round(saved + ?, 2))
               WHERE lower(name)=lower(?)""",
            (float(amount), (name or "").strip()),
        )
        if cur.rowcount == 0:
            return None
        await conn.commit()
        cur = await conn.execute(
            "SELECT name, saved, target FROM finance_goals WHERE lower(name)=lower(?)",
            ((name or "").strip(),),
        )
        stored_name, saved, target = await cur.fetchone()
    return {"name": stored_name, "saved": saved, "target": target,
            "reached": saved >= target}


async def delete_goal(name: str) -> bool:
    """Delete a savings goal by name. Returns False if there was no such goal."""
    async with connect() as conn:
        cur = await conn.execute(
            "DELETE FROM finance_goals WHERE lower(name)=lower(?)", ((name or "").strip(),)
        )
        await conn.commit()
        return cur.rowcount > 0


async def get_goals() -> list[dict]:
    """All goals with progress fields filled in, for display.

    Each goal gains ``remaining``, ``perc`` (saved as a percentage of target),
    ``months_left``, ``monthly_quota`` (what to set aside each month to finish on
    time), and ``reached``. ``monthly_quota`` is None when there's no deadline,
    and the full remaining amount when the deadline is already past.
    """
    today = date.today()
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT name, target, saved, target_date FROM finance_goals ORDER BY name"
        )
        rows = await cur.fetchall()

    goals = []
    for name, target, saved, target_date in rows:
        target = float(target)
        saved = round(float(saved), 2)
        remaining = round(max(target - saved, 0.0), 2)
        perc = round(saved / target * 100, 1) if target else 0.0
        months_left = _months_until(target_date, today) if target_date else None
        goals.append({
            "name": name, "target": target, "saved": saved,
            "remaining": remaining, "perc": perc, "target_date": target_date,
            "months_left": months_left,
            "monthly_quota": _monthly_quota(remaining, months_left),
            "reached": saved >= target,
        })
    return goals


def _monthly_quota(remaining: float, months_left: int | None) -> float | None:
    """How much to save each month to hit the goal on time.

    Zero once the goal is met, None when there's no deadline to pace against, and
    the whole remaining amount when the deadline has already passed.
    """
    if remaining <= 0:
        return 0.0
    if months_left is None:
        return None
    if months_left <= 0:
        return remaining
    return round(remaining / months_left, 2)
