"""Monthly budgets per category, and how the current month is tracking.

A budget is a monthly spending cap for one category. ``get_budget_status`` is
the interesting part: it compares each cap against what was actually spent in a
given month so the UI can show progress bars and flag overruns.
"""
from __future__ import annotations

from .categories import normalize_category
from ..db import connect


async def set_budget(category: str, amount: float) -> str:
    """Set (or replace) the monthly cap for a category; return the canonical name.

    The amount is stored as a positive number regardless of sign. To remove a
    budget use ``delete_budget`` rather than setting it to zero.
    """
    category = await normalize_category(category)
    async with connect() as conn:
        await conn.execute(
            """INSERT INTO finance_budgets (category, amount, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(category) DO UPDATE SET
                   amount=excluded.amount, updated_at=CURRENT_TIMESTAMP""",
            (category, abs(float(amount))),
        )
        await conn.commit()
    return category


async def delete_budget(category: str) -> bool:
    """Remove a category's budget. Returns False if it had none."""
    async with connect() as conn:
        cur = await conn.execute(
            "DELETE FROM finance_budgets WHERE lower(category)=lower(?)",
            ((category or "").strip().lower(),),
        )
        await conn.commit()
        return cur.rowcount > 0


async def list_budgets() -> list[dict]:
    """All budgets as ``{category, amount}``, alphabetically by category."""
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT category, amount FROM finance_budgets ORDER BY category"
        )
        return [{"category": r[0], "amount": r[1]} for r in await cur.fetchall()]


async def get_budget_status(year: int, month: int) -> list[dict]:
    """How each budgeted category is doing in the given month.

    For every budget, sums that month's expenses in its category and returns
    ``{category, budget, spent, remaining, perc, over}``, sorted with the worst
    overruns first so the UI can surface them. ``perc`` is spend as a percentage
    of the cap; ``over`` is True once spending exceeds it.
    """
    month_pattern = f"{int(year):04d}-{int(month):02d}-%"
    async with connect() as conn:
        cur = await conn.execute(
            """SELECT b.category, b.amount,
                      COALESCE(-SUM(CASE WHEN t.amount < 0 THEN t.amount END), 0)
               FROM finance_budgets b
               LEFT JOIN finance_transactions t
                 ON t.category = b.category AND t.date LIKE ?
               GROUP BY b.category, b.amount""",
            (month_pattern,),
        )
        rows = await cur.fetchall()

    statuses = []
    for category, budget, spent in rows:
        budget = float(budget)
        spent = round(float(spent), 2)
        remaining = round(budget - spent, 2)
        perc = round(spent / budget * 100, 1) if budget else 0.0
        statuses.append({
            "category": category, "budget": budget, "spent": spent,
            "remaining": remaining, "perc": perc, "over": spent > budget,
        })
    statuses.sort(key=lambda s: s["perc"], reverse=True)
    return statuses
