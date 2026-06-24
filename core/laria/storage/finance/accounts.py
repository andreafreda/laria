"""Bank accounts, cards, wallets, the places money sits.

An account holds an opening balance; its live balance is that opening figure
plus every transaction booked against it (see ``transactions.get_balance``).
Accounts are never auto-deleted while they still have transactions, so history
is never silently lost, deactivate them instead.
"""
from __future__ import annotations

from ..db import build_set_clause, connect


def _account_dict(row) -> dict:
    """Map a DB row to the account shape the rest of the app expects."""
    return {"id": row[0], "name": row[1], "type": row[2], "owner": row[3],
            "opening_balance": row[4], "active": bool(row[5])}


async def list_accounts(active_only: bool = True) -> list[dict]:
    """List accounts, by default only the active ones (the ones shown to users)."""
    async with connect() as conn:
        sql = ("SELECT id, name, type, owner, opening_balance, active "
               "FROM finance_accounts")
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY id"
        cur = await conn.execute(sql)
        rows = await cur.fetchall()
    return [_account_dict(r) for r in rows]


async def get_account(name: str) -> dict | None:
    """Fetch one account by its unique name, or None if there is no such account."""
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT id, name, type, owner, opening_balance, active "
            "FROM finance_accounts WHERE name=?",
            (name,),
        )
        row = await cur.fetchone()
    return _account_dict(row) if row else None


async def add_account(name: str, type: str, opening_balance: float = 0.0,
                      owner: str = "family") -> int:
    """Create an account (or reactivate and update one that already exists).

    Re-adding a previously deactivated account brings it back rather than
    failing on the unique name, which is what users expect when they "add it
    again". Returns the account id.
    """
    async with connect() as conn:
        await conn.execute(
            """INSERT INTO finance_accounts (name, type, owner, opening_balance, active)
               VALUES (?, ?, ?, ?, 1)
               ON CONFLICT(name) DO UPDATE SET
                   type=excluded.type, owner=excluded.owner,
                   opening_balance=excluded.opening_balance, active=1""",
            (name, type, owner, float(opening_balance)),
        )
        await conn.commit()
        cur = await conn.execute("SELECT id FROM finance_accounts WHERE name=?", (name,))
        return (await cur.fetchone())[0]


async def update_account(name: str, *, new_name: str | None = None,
                         type: str | None = None, owner: str | None = None,
                         opening_balance: float | None = None,
                         active: bool | None = None) -> bool:
    """Change only the fields you pass and leave the rest untouched.

    Returns False if the account doesn't exist or if ``new_name`` would collide
    with another account.
    """
    changes = {
        "name": new_name.strip() if new_name is not None else None,
        "type": type,
        "owner": owner,
        "opening_balance": float(opening_balance) if opening_balance is not None else None,
        "active": (1 if active else 0) if active is not None else None,
    }
    clause, params = build_set_clause(changes)
    if not clause:
        return False

    params.append(name)
    async with connect() as conn:
        try:
            cur = await conn.execute(
                f"UPDATE finance_accounts SET {clause} WHERE name=?", params
            )
        except Exception:  # IntegrityError: new_name already taken (UNIQUE)
            return False
        await conn.commit()
        return cur.rowcount > 0


async def delete_account(name: str) -> dict:
    """Delete an account, but only if it has no transactions.

    If transactions exist the account is kept and the result says so
    (``in_use``), deactivate it with ``update_account(active=False)`` to hide it
    without throwing away its history. Result shapes:
    ``{ok: True}`` / ``{ok: False, found: False}`` / ``{ok: False, in_use: True, transactions: N}``.
    """
    account = await get_account(name)
    if account is None:
        return {"ok": False, "found": False}
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT count(*) FROM finance_transactions WHERE account_id=?", (account["id"],)
        )
        transaction_count = (await cur.fetchone())[0]
        if transaction_count > 0:
            return {"ok": False, "in_use": True, "transactions": transaction_count}
        await conn.execute("DELETE FROM finance_accounts WHERE id=?", (account["id"],))
        await conn.commit()
    return {"ok": True}
