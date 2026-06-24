"""Transactions — the individual money movements booked against an account.

Amounts are signed: positive is money in (income), negative is money out
(expense). Everything else in finance — balances, budgets, reports — is derived
from these rows.
"""
from __future__ import annotations

from .accounts import get_account
from .rules import list_rules, match_rule
from ..db import connect


async def add_transaction(account: str, date: str, amount: float,
                          category: str, description: str = "") -> int:
    """Record one movement on an account; return its new id.

    ``amount`` is signed (+ income, - expense). Raises ValueError if the account
    name is unknown, so a typo can't silently create an orphan row.
    """
    account_row = await get_account(account)
    if account_row is None:
        raise ValueError(f"unknown account: {account}")
    async with connect() as conn:
        cur = await conn.execute(
            """INSERT INTO finance_transactions
               (account_id, date, amount, category, description)
               VALUES (?, ?, ?, ?, ?)""",
            (account_row["id"], date, float(amount), category, description),
        )
        await conn.commit()
        return cur.lastrowid


async def get_balance(account: str) -> float:
    """Current balance of an account = its opening balance plus all movements."""
    account_row = await get_account(account)
    if account_row is None:
        raise ValueError(f"unknown account: {account}")
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM finance_transactions WHERE account_id=?",
            (account_row["id"],),
        )
        movements_total = (await cur.fetchone())[0]
    return round(account_row["opening_balance"] + movements_total, 2)


async def list_transactions(account: str | None = None, date_from: str | None = None,
                            date_to: str | None = None, category: str | None = None,
                            limit: int = 100) -> list[dict]:
    """List transactions newest-first, narrowed by any combination of filters.

    All filters are optional; omitting them returns the latest ``limit`` rows
    across all accounts.
    """
    sql = """SELECT t.id, a.name, t.date, t.amount, t.category, t.description
             FROM finance_transactions t JOIN finance_accounts a ON a.id = t.account_id
             WHERE 1=1"""
    params: list = []
    if account:
        sql += " AND a.name=?"; params.append(account)
    if date_from:
        sql += " AND t.date>=?"; params.append(date_from)
    if date_to:
        sql += " AND t.date<=?"; params.append(date_to)
    if category:
        sql += " AND t.category=?"; params.append(category)
    sql += " ORDER BY t.date DESC, t.id DESC LIMIT ?"
    params.append(int(limit))
    async with connect() as conn:
        cur = await conn.execute(sql, params)
        rows = await cur.fetchall()
    return [
        {"id": r[0], "account": r[1], "date": r[2], "amount": r[3],
         "category": r[4], "description": r[5]}
        for r in rows
    ]


async def delete_transaction(transaction_id: int) -> bool:
    """Delete one transaction by id. Returns False if there was no such row."""
    async with connect() as conn:
        cur = await conn.execute(
            "DELETE FROM finance_transactions WHERE id=?", (transaction_id,)
        )
        await conn.commit()
        return cur.rowcount > 0


async def update_transaction(transaction_id: int, *, date: str | None = None,
                             amount: float | None = None, category: str | None = None,
                             description: str | None = None,
                             account: str | None = None) -> bool:
    """Change only the fields you pass on an existing transaction.

    Returns False if the id doesn't exist or if a given account name is unknown.
    Moving a transaction to another account is done by name and resolved to its id.
    """
    changes: list[str] = []
    values: list = []
    if date is not None:
        changes.append("date=?"); values.append(date)
    if amount is not None:
        changes.append("amount=?"); values.append(float(amount))
    if category is not None:
        changes.append("category=?"); values.append(category)
    if description is not None:
        changes.append("description=?"); values.append(description)
    if account is not None:
        account_row = await get_account(account)
        if account_row is None:
            return False
        changes.append("account_id=?"); values.append(account_row["id"])
    if not changes:
        return False

    values.append(int(transaction_id))
    async with connect() as conn:
        cur = await conn.execute(
            f"UPDATE finance_transactions SET {', '.join(changes)} WHERE id=?", values
        )
        await conn.commit()
        return cur.rowcount > 0


async def import_transactions(account: str, movements: list[dict]) -> dict:
    """Bulk-import movements from a parsed bank statement, skipping duplicates.

    Each movement is ``{date, amount, description, category, hash}``. The
    ``hash`` deduplicates per account, so re-importing the same statement file
    won't create doubles. A matching auto-categorization rule overrides the
    parser's guessed category. Returns ``{inserted, duplicates, total}``.
    """
    account_row = await get_account(account)
    if account_row is None:
        raise ValueError(f"unknown account: {account}")
    account_id = account_row["id"]
    rules = await list_rules()
    inserted = duplicates = 0
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT import_hash FROM finance_transactions "
            "WHERE account_id=? AND import_hash IS NOT NULL",
            (account_id,),
        )
        seen_hashes = {r[0] for r in await cur.fetchall()}
        for movement in movements:
            movement_hash = movement.get("hash")
            if movement_hash and movement_hash in seen_hashes:
                duplicates += 1
                continue
            if movement_hash:
                seen_hashes.add(movement_hash)

            category = (match_rule(movement.get("description"), rules)
                        or (movement.get("category") or "misc").strip().lower())
            await conn.execute(
                "INSERT OR IGNORE INTO finance_categories (name) VALUES (?)", (category,)
            )
            await conn.execute(
                """INSERT INTO finance_transactions
                   (account_id, date, amount, category, description, import_hash)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (account_id, movement["date"], float(movement["amount"]), category,
                 (movement.get("description") or "").strip(), movement_hash),
            )
            inserted += 1
        await conn.commit()
    return {"inserted": inserted, "duplicates": duplicates, "total": len(movements)}
