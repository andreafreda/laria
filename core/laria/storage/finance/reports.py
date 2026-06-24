"""Read-only views over finance data: balances, summaries, trends, history.

Nothing here changes data except ``reset_finance`` (a deliberate wipe for ending
a test run). Reports exclude internal transfers between the household's own
accounts, since those are neither income nor spending, except balances, which
always count every movement.
"""
from __future__ import annotations

from datetime import date

from .. import db
from ..db import CATEGORY_TRANSFER, connect

MAX_MATRIX_MONTHS = 120  # safety cap for "whole history" (10 years)


async def reset_finance(reset_categories: bool = False,
                        reset_balances: bool = False) -> dict:
    """Wipe finance data, meant for ending a test run, not everyday use.

    Always clears transactions, budgets and goals. Optionally also restores the
    default category set and zeroes every account's opening balance. Returns a
    count of what was removed so the caller can confirm the damage.
    """
    async with connect() as conn:
        transactions_deleted = await _count_then_delete(conn, "finance_transactions")
        budgets_deleted = await _count_then_delete(conn, "finance_budgets")
        goals_deleted = await _count_then_delete(conn, "finance_goals")

        categories_reset = 0
        if reset_categories:
            categories_reset = await _count_then_delete(conn, "finance_categories")
            for category in db.DEFAULT_CATEGORIES:
                await conn.execute(
                    "INSERT OR IGNORE INTO finance_categories (name) VALUES (?)", (category,)
                )

        balances_zeroed = 0
        if reset_balances:
            cur = await conn.execute(
                "SELECT count(*) FROM finance_accounts WHERE opening_balance != 0"
            )
            balances_zeroed = (await cur.fetchone())[0]
            await conn.execute("UPDATE finance_accounts SET opening_balance = 0")

        await conn.commit()
    return {"transactions_deleted": transactions_deleted, "budgets_deleted": budgets_deleted,
            "goals_deleted": goals_deleted, "categories_reset": categories_reset,
            "balances_zeroed": balances_zeroed}


async def _count_then_delete(conn, table: str) -> int:
    """Count a table's rows, delete them all, and return the count (for reset)."""
    cur = await conn.execute(f"SELECT count(*) FROM {table}")
    count = (await cur.fetchone())[0]
    await conn.execute(f"DELETE FROM {table}")
    return count


async def get_balances() -> list[dict]:
    """Current balance of every active account as ``{account, type, owner, balance}``."""
    async with connect() as conn:
        cur = await conn.execute(
            """SELECT a.name, a.type, a.owner,
                      a.opening_balance + COALESCE(SUM(t.amount), 0)
               FROM finance_accounts a
               LEFT JOIN finance_transactions t ON t.account_id = a.id
               WHERE a.active = 1
               GROUP BY a.id
               ORDER BY a.id"""
        )
        rows = await cur.fetchall()
    return [{"account": r[0], "type": r[1], "owner": r[2], "balance": round(r[3], 2)}
            for r in rows]


async def balances_by_owner() -> dict:
    """Total money held per owner, e.g. ``{"family": 1200.0, "alice": 300.0}``."""
    totals: dict = {}
    for account in await get_balances():
        owner = account["owner"]
        totals[owner] = round(totals.get(owner, 0.0) + account["balance"], 2)
    return totals


async def expense_summary(date_from: str | None = None, date_to: str | None = None,
                          account: str | None = None, owner: str | None = None) -> dict:
    """Income, expenses, net and a per-category expense breakdown for a period.

    All filters are optional. Internal transfers are excluded. Returns
    ``{income, expenses, net, by_category}`` where ``expenses`` is negative and
    ``by_category`` lists only spending (negative) totals, biggest first.
    """
    where, params = _expense_filter(date_from, date_to, account, owner)
    from_join = (f"FROM finance_transactions t "
                 f"JOIN finance_accounts a ON a.id = t.account_id {where}")
    async with connect() as conn:
        cur = await conn.execute(
            f"""SELECT
                  COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount END), 0),
                  COALESCE(SUM(CASE WHEN t.amount < 0 THEN t.amount END), 0)
                {from_join}""",
            params,
        )
        income, expenses = await cur.fetchone()
        income, expenses = float(income), float(expenses)

        cur = await conn.execute(
            f"""SELECT t.category, SUM(t.amount) total
                {from_join} AND t.amount < 0
                GROUP BY t.category ORDER BY total ASC""",
            params,
        )
        by_category = [{"category": r[0], "total": round(r[1], 2)}
                       for r in await cur.fetchall()]
    return {
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "net": round(income + expenses, 2),
        "by_category": by_category,
    }


def _expense_filter(date_from: str | None, date_to: str | None,
                    account: str | None, owner: str | None) -> tuple[str, list]:
    """Build the shared WHERE clause + params used by the expense reports.

    Always excludes internal transfers, then adds whichever of account / owner /
    date range were supplied. Returned as ``(where_sql, params)`` to drop into a
    query (the join aliases transactions ``t`` and accounts ``a``).
    """
    where = "WHERE t.category!=?"
    params: list = [CATEGORY_TRANSFER]
    if account:
        where += " AND a.name=?"; params.append(account)
    if owner:
        where += " AND a.owner=?"; params.append(owner)
    if date_from:
        where += " AND t.date>=?"; params.append(date_from)
    if date_to:
        where += " AND t.date<=?"; params.append(date_to)
    return where, params


async def monthly_trend(year: int, owner: str | None = None) -> list[dict]:
    """Income, expenses and net for each of the 12 months of a year.

    Always returns 12 rows (months with no activity are zeros), so charts have a
    full axis. Optionally filtered to one owner. Excludes internal transfers.
    """
    where = "WHERE t.date LIKE ? AND t.category!=?"
    params: list = [f"{int(year):04d}-%", CATEGORY_TRANSFER]
    if owner:
        where += " AND a.owner=?"; params.append(owner)

    months = [{"month": m, "income": 0.0, "expenses": 0.0, "net": 0.0}
              for m in range(1, 13)]
    async with connect() as conn:
        cur = await conn.execute(
            f"""SELECT CAST(substr(t.date, 6, 2) AS INTEGER) month,
                       COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount END), 0),
                       COALESCE(SUM(CASE WHEN t.amount < 0 THEN -t.amount END), 0)
                FROM finance_transactions t JOIN finance_accounts a ON a.id = t.account_id
                {where}
                GROUP BY month""",
            params,
        )
        for month, income, expenses in await cur.fetchall():
            if 1 <= month <= 12:
                row = months[month - 1]
                row["income"] = round(float(income), 2)
                row["expenses"] = round(float(expenses), 2)
                row["net"] = round(float(income) - float(expenses), 2)
    return months


async def category_spending_year(year: int, owner: str | None = None) -> list[dict]:
    """Per-category spending for a year, with a 12-month breakdown each.

    Returns ``[{category, total, months:[12]}]`` sorted by total spend, biggest
    first, the data behind a "where did the money go this year" view. Optionally
    filtered to one owner; excludes internal transfers.
    """
    where = "WHERE t.amount < 0 AND t.date LIKE ? AND t.category!=?"
    params: list = [f"{int(year):04d}-%", CATEGORY_TRANSFER]
    if owner:
        where += " AND a.owner=?"; params.append(owner)

    by_category: dict = {}
    async with connect() as conn:
        cur = await conn.execute(
            f"""SELECT t.category, CAST(substr(t.date, 6, 2) AS INTEGER) month,
                       SUM(-t.amount)
                FROM finance_transactions t JOIN finance_accounts a ON a.id = t.account_id
                {where}
                GROUP BY t.category, month""",
            params,
        )
        for category, month, spent in await cur.fetchall():
            entry = by_category.setdefault(
                category, {"category": category, "total": 0.0, "months": [0.0] * 12}
            )
            if 1 <= month <= 12:
                entry["months"][month - 1] = round(float(spent), 2)
                entry["total"] = round(entry["total"] + float(spent), 2)
    return sorted(by_category.values(), key=lambda c: c["total"], reverse=True)


async def years_with_data() -> list[int]:
    """Distinct years that have any transactions, for a year navigator."""
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT DISTINCT CAST(substr(date, 1, 4) AS INTEGER) year "
            "FROM finance_transactions ORDER BY year"
        )
        return [r[0] for r in await cur.fetchall()]


async def monthly_category_matrix(months: int | None = None) -> dict:
    """Spending laid out as a category x month grid, for a stacked chart.

    ``months=None`` covers the whole history (from the first transaction to this
    month) so adding a month never drops earlier ones; ``months=N`` keeps only
    the last N. Returns ``{months: ["YYYY-MM"...], categories: {cat: [per-month]},
    totals: [per-month]}`` with categories ordered by overall spend. Excludes
    internal transfers.
    """
    month_labels = await _recent_month_labels(months)
    column_for_month = {label: i for i, label in enumerate(month_labels)}

    per_category: dict = {}
    totals = [0.0] * len(month_labels)
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT substr(date,1,7) month, category, SUM(-amount) "
            "FROM finance_transactions "
            "WHERE amount<0 AND category!=? AND substr(date,1,7)>=? "
            "GROUP BY month, category",
            (CATEGORY_TRANSFER, month_labels[0]),
        )
        for month, category, spent in await cur.fetchall():
            if month not in column_for_month:
                continue
            column = column_for_month[month]
            row = per_category.setdefault(category, [0.0] * len(month_labels))
            row[column] = round(float(spent), 2)
            totals[column] = round(totals[column] + float(spent), 2)

    per_category = dict(sorted(per_category.items(), key=lambda kv: -sum(kv[1])))
    return {"months": month_labels, "categories": per_category, "totals": totals}


async def _recent_month_labels(months: int | None) -> list[str]:
    """The "YYYY-MM" labels to show, oldest first.

    With an explicit ``months`` we take that many ending this month; with None we
    span the whole history (capped at MAX_MATRIX_MONTHS), so the matrix grows as
    data accrues instead of dropping old columns.
    """
    today = date.today()
    if months is None:
        months = await _months_since_first_transaction(today)
    return _months_ending_at(today, months)


async def _months_since_first_transaction(today: date) -> int:
    """Count of months from the earliest transaction to today (at least 1)."""
    async with connect() as conn:
        cur = await conn.execute("SELECT MIN(substr(date,1,7)) FROM finance_transactions")
        first = (await cur.fetchone())[0]
    if not first:
        return 1
    first_year, first_month = int(first[:4]), int(first[5:7])
    span = (today.year - first_year) * 12 + (today.month - first_month) + 1
    return max(1, min(span, MAX_MATRIX_MONTHS))


def _months_ending_at(today: date, count: int) -> list[str]:
    """The last ``count`` "YYYY-MM" labels ending at ``today``, oldest first."""
    labels = []
    year, month = today.year, today.month
    for _ in range(count):
        labels.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    labels.reverse()
    return labels


async def recent_transactions(months: int | None = None) -> list[dict]:
    """Individual expenses, newest first, for a drill-down by category or month.

    ``months=None`` returns the whole history; ``months=N`` only the last N
    months. Excludes internal transfers. Each item is
    ``{date, amount, category, description}`` with a positive amount.
    """
    earliest = "0000-00-00"
    if months is not None:
        earliest = _first_day_n_months_back(date.today(), months)
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT date, -amount, category, description FROM finance_transactions "
            "WHERE amount<0 AND category!=? AND date>=? ORDER BY date DESC",
            (CATEGORY_TRANSFER, earliest),
        )
        rows = await cur.fetchall()
    return [
        {"date": row[0], "amount": round(float(row[1]), 2), "category": row[2],
         "description": (row[3] or "").strip()}
        for row in rows
    ]


def _first_day_n_months_back(today: date, months: int) -> str:
    """First day (YYYY-MM-01) of the month ``months`` ago, counting this month."""
    year, month = today.year, today.month
    month -= (months - 1)
    while month <= 0:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}-01"
