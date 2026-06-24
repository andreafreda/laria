"""Finance storage: accounts, transactions, categories, rules, budgets, goals,
reports. Ported from HARIA ``memory/econ.py`` (IT) and translated to EN.

Amounts are signed: positive = income, negative = expense. Internal transfers
use the ``transfer`` category and are excluded from expense/income reports (but
always counted in balances).
"""
from __future__ import annotations

import collections
from datetime import date

from . import db
from .db import CATEGORY_TRANSFER, connect


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #

def _account_dict(r) -> dict:
    return {"id": r[0], "name": r[1], "type": r[2], "owner": r[3],
            "opening_balance": r[4], "active": bool(r[5])}


async def list_accounts(active_only: bool = True) -> list[dict]:
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
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT id, name, type, owner, opening_balance, active "
            "FROM finance_accounts WHERE name=?",
            (name,),
        )
        r = await cur.fetchone()
    return _account_dict(r) if r else None


async def add_account(name: str, type: str, opening_balance: float = 0.0,
                      owner: str = "family") -> int:
    """Create (or reactivate) an account."""
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
    """Update the supplied fields of an account (others unchanged).
    False if the account does not exist or the new name collides."""
    sets, params = [], []
    if new_name is not None:
        sets.append("name=?"); params.append(new_name.strip())
    if type is not None:
        sets.append("type=?"); params.append(type)
    if owner is not None:
        sets.append("owner=?"); params.append(owner)
    if opening_balance is not None:
        sets.append("opening_balance=?"); params.append(float(opening_balance))
    if active is not None:
        sets.append("active=?"); params.append(1 if active else 0)
    if not sets:
        return False
    params.append(name)
    async with connect() as conn:
        try:
            cur = await conn.execute(
                f"UPDATE finance_accounts SET {', '.join(sets)} WHERE name=?", params
            )
        except Exception:  # IntegrityError: new_name collides (UNIQUE)
            return False
        await conn.commit()
        return cur.rowcount > 0


async def delete_account(name: str) -> dict:
    """Delete an account. If it has transactions it is NOT deleted
    (returns in_use=True): use update_account(active=False) instead."""
    acc = await get_account(name)
    if acc is None:
        return {"ok": False, "found": False}
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT count(*) FROM finance_transactions WHERE account_id=?", (acc["id"],)
        )
        n = (await cur.fetchone())[0]
        if n > 0:
            return {"ok": False, "in_use": True, "transactions": n}
        await conn.execute("DELETE FROM finance_accounts WHERE id=?", (acc["id"],))
        await conn.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Transactions
# --------------------------------------------------------------------------- #

async def add_transaction(account: str, date: str, amount: float,
                          category: str, description: str = "") -> int:
    """Record a movement. Signed amount: + income, - expense."""
    acc = await get_account(account)
    if acc is None:
        raise ValueError(f"unknown account: {account}")
    async with connect() as conn:
        cur = await conn.execute(
            """INSERT INTO finance_transactions
               (account_id, date, amount, category, description)
               VALUES (?, ?, ?, ?, ?)""",
            (acc["id"], date, float(amount), category, description),
        )
        await conn.commit()
        return cur.lastrowid


async def get_balance(account: str) -> float:
    """Balance = opening_balance + sum(transactions)."""
    acc = await get_account(account)
    if acc is None:
        raise ValueError(f"unknown account: {account}")
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM finance_transactions WHERE account_id=?",
            (acc["id"],),
        )
        total = (await cur.fetchone())[0]
    return round(acc["opening_balance"] + total, 2)


async def list_transactions(account: str | None = None, date_from: str | None = None,
                            date_to: str | None = None, category: str | None = None,
                            limit: int = 100) -> list[dict]:
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
    """Update the supplied fields. False if the id is missing or the account
    is unknown."""
    sets, params = [], []
    if date is not None:
        sets.append("date=?"); params.append(date)
    if amount is not None:
        sets.append("amount=?"); params.append(float(amount))
    if category is not None:
        sets.append("category=?"); params.append(category)
    if description is not None:
        sets.append("description=?"); params.append(description)
    if account is not None:
        acc = await get_account(account)
        if acc is None:
            return False
        sets.append("account_id=?"); params.append(acc["id"])
    if not sets:
        return False
    params.append(int(transaction_id))
    async with connect() as conn:
        cur = await conn.execute(
            f"UPDATE finance_transactions SET {', '.join(sets)} WHERE id=?", params
        )
        await conn.commit()
        return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# Categorization rules
# --------------------------------------------------------------------------- #

async def add_rule(keyword: str, category: str) -> str:
    """Categorization rule: every movement whose description contains ``keyword``
    (case-insensitive) is filed under ``category`` on import."""
    kw = (keyword or "").strip().lower()
    cat = (category or "").strip().lower()
    if not kw or not cat:
        raise ValueError("keyword and category are required")
    if len(kw) < 3:
        raise ValueError("keyword too short: minimum 3 characters")
    async with connect() as conn:
        await conn.execute("INSERT OR IGNORE INTO finance_categories (name) VALUES (?)", (cat,))
        await conn.execute(
            "INSERT INTO finance_rules (keyword, category) VALUES (?, ?) "
            "ON CONFLICT(keyword) DO UPDATE SET category=excluded.category",
            (kw, cat),
        )
        await conn.commit()
    return cat


async def delete_rule(keyword: str) -> bool:
    async with connect() as conn:
        cur = await conn.execute(
            "DELETE FROM finance_rules WHERE keyword=?", ((keyword or "").strip().lower(),)
        )
        await conn.commit()
        return cur.rowcount > 0


async def list_rules() -> list[dict]:
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT keyword, category FROM finance_rules ORDER BY length(keyword) DESC"
        )
        return [{"keyword": r[0], "category": r[1]} for r in await cur.fetchall()]


def _match_rule(description: str, rules: list[dict]) -> str | None:
    """Category of the first rule (longest keyword) contained in description."""
    d = (description or "").lower()
    for r in rules:  # already ordered by longest (most specific) keyword
        if r["keyword"] in d:
            return r["category"]
    return None


async def apply_rules() -> dict:
    """Re-apply rules to ALL existing transactions. Returns update count per
    category."""
    rules = await list_rules()
    if not rules:
        return {}
    out = collections.Counter()
    async with connect() as conn:
        cur = await conn.execute("SELECT id, description, category FROM finance_transactions")
        rows = await cur.fetchall()
        for tid, descr, cat in rows:
            new = _match_rule(descr, rules)
            if new and new != cat:
                await conn.execute(
                    "UPDATE finance_transactions SET category=? WHERE id=?", (new, tid)
                )
                out[new] += 1
        await conn.commit()
    return dict(out)


async def apply_rule(keyword: str) -> int:
    """Apply ONE rule to existing transactions. Returns count updated. Used on
    rule creation: unlike apply_rules it doesn't touch other already-correct
    categories."""
    kw = (keyword or "").strip().lower()
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT category FROM finance_rules WHERE keyword=?", (kw,))
        row = await cur.fetchone()
        if not row:
            return 0
        cat = row[0]
        cur = await conn.execute(
            "UPDATE finance_transactions SET category=? "
            "WHERE category!=? AND instr(lower(description), ?) > 0",
            (cat, cat, kw),
        )
        await conn.commit()
        return cur.rowcount


async def import_transactions(account: str, movements: list[dict]) -> dict:
    """Bulk import movements from a bank statement. Each movement:
    {date, amount, description, category, hash}. Dedup via import_hash (per
    account): re-importing the same file doesn't duplicate. Returns
    {inserted, duplicates, total}."""
    acc = await get_account(account)
    if acc is None:
        raise ValueError(f"unknown account: {account}")
    aid = acc["id"]
    rules = await list_rules()  # rule overrides parser-guessed category
    inserted = duplicates = 0
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT import_hash FROM finance_transactions "
            "WHERE account_id=? AND import_hash IS NOT NULL",
            (aid,),
        )
        existing = {r[0] for r in await cur.fetchall()}
        for m in movements:
            h = m.get("hash")
            if h and h in existing:
                duplicates += 1
                continue
            if h:
                existing.add(h)
            cat = (_match_rule(m.get("description"), rules)
                   or (m.get("category") or "misc").strip().lower())
            await conn.execute(
                "INSERT OR IGNORE INTO finance_categories (name) VALUES (?)", (cat,)
            )
            await conn.execute(
                """INSERT INTO finance_transactions
                   (account_id, date, amount, category, description, import_hash)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (aid, m["date"], float(m["amount"]), cat,
                 (m.get("description") or "").strip(), h),
            )
            inserted += 1
        await conn.commit()
    return {"inserted": inserted, "duplicates": duplicates, "total": len(movements)}


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #

async def list_categories() -> list[str]:
    async with connect() as conn:
        cur = await conn.execute("SELECT name FROM finance_categories ORDER BY name")
        return [r[0] for r in await cur.fetchall()]


async def normalize_category(name: str) -> str:
    """Return the canonical category. Case-insensitive match against existing
    ones; if new, register it (trimmed/lowercase) and return it."""
    raw = (name or "").strip()
    if not raw:
        raw = "misc"
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (raw,)
        )
        row = await cur.fetchone()
        if row:
            return row[0]
        canon = raw.lower()
        await conn.execute(
            "INSERT OR IGNORE INTO finance_categories (name) VALUES (?)", (canon,)
        )
        await conn.commit()
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (canon,)
        )
        row = await cur.fetchone()
        return row[0] if row else canon


async def delete_category(name: str) -> dict:
    """Delete a category. If used by transactions/rules it is NOT deleted
    (returns in_use + count): rename/merge to move them first."""
    cat = (name or "").strip()
    if cat.lower() == CATEGORY_TRANSFER:
        return {"ok": False, "protected": True}
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (cat,)
        )
        row = await cur.fetchone()
        if not row:
            return {"ok": False, "found": False}
        canon = row[0]
        cur = await conn.execute(
            "SELECT count(*) FROM finance_transactions WHERE category=?", (canon,)
        )
        n = (await cur.fetchone())[0]
        if n > 0:
            return {"ok": False, "in_use": True, "transactions": n}
        cur = await conn.execute(
            "SELECT count(*) FROM finance_rules WHERE category=?", (canon,)
        )
        nr = (await cur.fetchone())[0]
        if nr > 0:
            return {"ok": False, "in_use_rules": True, "rules": nr}
        await conn.execute("DELETE FROM finance_categories WHERE name=?", (canon,))
        await conn.commit()
    return {"ok": True}


async def rename_category(old: str, new: str) -> bool:
    """Rename a category + propagate to all transactions. False if 'old' is
    missing. If 'new' exists this acts as a merge."""
    new = (new or "").strip().lower()
    if not new:
        return False
    if (old or "").strip().lower() == CATEGORY_TRANSFER:
        return False  # system category: keeps transfers out of reports
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (old,)
        )
        row = await cur.fetchone()
        if not row:
            return False
        old_canon = row[0]
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (new,)
        )
        exists = await cur.fetchone()
        await conn.execute(
            "UPDATE finance_transactions SET category=? WHERE category=?", (new, old_canon)
        )
        await conn.execute(
            "UPDATE finance_rules SET category=? WHERE category=?", (new, old_canon)
        )
        if exists:
            await conn.execute("DELETE FROM finance_categories WHERE name=?", (old_canon,))
        else:
            await conn.execute(
                "UPDATE finance_categories SET name=? WHERE name=?", (new, old_canon)
            )
        await conn.commit()
        return True


async def merge_category(src: str, dst: str) -> bool:
    """Move all transactions from 'src' to 'dst' and delete 'src'. False if src
    is missing. 'dst' is created if it doesn't exist."""
    if (src or "").strip().lower() == CATEGORY_TRANSFER:
        return False  # system category
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (src,)
        )
        srow = await cur.fetchone()
        if not srow:
            return False
        src_canon = srow[0]
        dst_canon = (dst or "").strip().lower()
        if not dst_canon or dst_canon == src_canon.lower():
            return False
        await conn.execute(
            "INSERT OR IGNORE INTO finance_categories (name) VALUES (?)", (dst_canon,)
        )
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (dst_canon,)
        )
        dst_canon = (await cur.fetchone())[0]
        await conn.execute(
            "UPDATE finance_transactions SET category=? WHERE category=?", (dst_canon, src_canon)
        )
        await conn.execute(
            "UPDATE finance_rules SET category=? WHERE category=?", (dst_canon, src_canon)
        )
        await conn.execute("DELETE FROM finance_categories WHERE name=?", (src_canon,))
        await conn.commit()
        return True


# --------------------------------------------------------------------------- #
# Budgets
# --------------------------------------------------------------------------- #

async def set_budget(category: str, amount: float) -> str:
    """Upsert the monthly budget for a category (stored as absolute value).
    Removal is via delete_budget. Returns the canonical category used."""
    cat = await normalize_category(category)
    async with connect() as conn:
        await conn.execute(
            """INSERT INTO finance_budgets (category, amount, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(category) DO UPDATE SET
                   amount=excluded.amount, updated_at=CURRENT_TIMESTAMP""",
            (cat, abs(float(amount))),
        )
        await conn.commit()
    return cat


async def delete_budget(category: str) -> bool:
    cat = (category or "").strip().lower()
    async with connect() as conn:
        cur = await conn.execute(
            "DELETE FROM finance_budgets WHERE lower(category)=lower(?)", (cat,)
        )
        await conn.commit()
        return cur.rowcount > 0


async def list_budgets() -> list[dict]:
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT category, amount FROM finance_budgets ORDER BY category"
        )
        return [{"category": r[0], "amount": r[1]} for r in await cur.fetchall()]


async def get_budget_status(year: int, month: int) -> list[dict]:
    """Per budgeted category: spent (month expenses), budget, remaining, perc.
    Sorted by perc descending (overruns first)."""
    ym = f"{int(year):04d}-{int(month):02d}-%"
    async with connect() as conn:
        cur = await conn.execute(
            """SELECT b.category, b.amount,
                      COALESCE(-SUM(CASE WHEN t.amount < 0 THEN t.amount END), 0)
               FROM finance_budgets b
               LEFT JOIN finance_transactions t
                 ON t.category = b.category AND t.date LIKE ?
               GROUP BY b.category, b.amount""",
            (ym,),
        )
        rows = await cur.fetchall()
    out = []
    for cat, budget, spent in rows:
        budget = float(budget)
        spent = round(float(spent), 2)
        remaining = round(budget - spent, 2)
        perc = round(spent / budget * 100, 1) if budget else 0.0
        out.append({
            "category": cat, "budget": budget, "spent": spent,
            "remaining": remaining, "perc": perc, "over": spent > budget,
        })
    out.sort(key=lambda x: x["perc"], reverse=True)
    return out


# --------------------------------------------------------------------------- #
# Savings goals
# --------------------------------------------------------------------------- #

def _months_left(target_date: str, today: date) -> int:
    """Whole months left until target_date. 0 if past/today."""
    try:
        d = date.fromisoformat(target_date)
    except (ValueError, TypeError):
        return 0
    if d <= today:
        return 0
    months = (d.year - today.year) * 12 + (d.month - today.month)
    if d.day < today.day:
        months -= 1
    return max(months, 1)


async def set_goal(name: str, target: float, target_date: str | None = None) -> int:
    """Create or update (target/deadline) a savings goal. Does not touch the
    existing saved amount. Returns the id."""
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
    """Add (or subtract if amount<0) to a goal's saved amount. Floored at 0.
    None if the goal doesn't exist."""
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
        name_db, saved, target = await cur.fetchone()
    return {"name": name_db, "saved": saved, "target": target,
            "reached": saved >= target}


async def delete_goal(name: str) -> bool:
    async with connect() as conn:
        cur = await conn.execute(
            "DELETE FROM finance_goals WHERE lower(name)=lower(?)", ((name or "").strip(),)
        )
        await conn.commit()
        return cur.rowcount > 0


async def get_goals() -> list[dict]:
    """Goals with computed fields: remaining, perc, months_left, suggested
    monthly_quota = remaining / months_left."""
    today = date.today()
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT name, target, saved, target_date FROM finance_goals ORDER BY name"
        )
        rows = await cur.fetchall()
    out = []
    for name, target, saved, tdate in rows:
        target = float(target)
        saved = round(float(saved), 2)
        remaining = round(max(target - saved, 0.0), 2)
        perc = round(saved / target * 100, 1) if target else 0.0
        months = _months_left(tdate, today) if tdate else None
        if remaining <= 0:
            quota = 0.0
        elif months is None:
            quota = None
        elif months <= 0:
            quota = remaining  # past due: need it all now
        else:
            quota = round(remaining / months, 2)
        out.append({
            "name": name, "target": target, "saved": saved,
            "remaining": remaining, "perc": perc, "target_date": tdate,
            "months_left": months, "monthly_quota": quota,
            "reached": saved >= target,
        })
    return out


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #

async def reset_finance(reset_categories: bool = False,
                        reset_balances: bool = False) -> dict:
    """Reset finance data. Always clears transactions, budgets and goals.
    Optional: restore default categories, zero opening balances. Returns counts."""
    async with connect() as conn:
        cur = await conn.execute("SELECT count(*) FROM finance_transactions")
        n_tx = (await cur.fetchone())[0]
        await conn.execute("DELETE FROM finance_transactions")
        cur = await conn.execute("SELECT count(*) FROM finance_budgets")
        n_budget = (await cur.fetchone())[0]
        await conn.execute("DELETE FROM finance_budgets")
        cur = await conn.execute("SELECT count(*) FROM finance_goals")
        n_goals = (await cur.fetchone())[0]
        await conn.execute("DELETE FROM finance_goals")
        n_cat = 0
        if reset_categories:
            cur = await conn.execute("SELECT count(*) FROM finance_categories")
            n_cat = (await cur.fetchone())[0]
            await conn.execute("DELETE FROM finance_categories")
            for cat in db.DEFAULT_CATEGORIES:
                await conn.execute(
                    "INSERT OR IGNORE INTO finance_categories (name) VALUES (?)", (cat,)
                )
        n_balances = 0
        if reset_balances:
            cur = await conn.execute(
                "SELECT count(*) FROM finance_accounts WHERE opening_balance != 0"
            )
            n_balances = (await cur.fetchone())[0]
            await conn.execute("UPDATE finance_accounts SET opening_balance = 0")
        await conn.commit()
    return {"transactions_deleted": n_tx, "budgets_deleted": n_budget,
            "goals_deleted": n_goals, "categories_reset": n_cat,
            "balances_zeroed": n_balances}


async def get_balances() -> list[dict]:
    """Balance of all active accounts: [{account, type, owner, balance}]."""
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
    """Total balance aggregated per owner: {owner: balance}."""
    out: dict = {}
    for s in await get_balances():
        out[s["owner"]] = round(out.get(s["owner"], 0.0) + s["balance"], 2)
    return out


async def expense_summary(date_from: str | None = None, date_to: str | None = None,
                          account: str | None = None, owner: str | None = None) -> dict:
    """Aggregate movements in the period: total income/expenses/net + expense
    breakdown per category (negative amounts only). Excludes internal transfers."""
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
    base = f"FROM finance_transactions t JOIN finance_accounts a ON a.id = t.account_id {where}"
    async with connect() as conn:
        cur = await conn.execute(
            f"""SELECT
                  COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount END), 0),
                  COALESCE(SUM(CASE WHEN t.amount < 0 THEN t.amount END), 0)
                {base}""",
            params,
        )
        income, expenses = await cur.fetchone()
        income, expenses = float(income), float(expenses)
        cur = await conn.execute(
            f"""SELECT t.category, SUM(t.amount) tot
                {base} AND t.amount < 0
                GROUP BY t.category ORDER BY tot ASC""",
            params,
        )
        cats = [{"category": r[0], "total": round(r[1], 2)} for r in await cur.fetchall()]
    return {
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "net": round(income + expenses, 2),
        "by_category": cats,
    }


async def monthly_trend(year: int, owner: str | None = None) -> list[dict]:
    """For the 12 months of the year: income, expenses, net. Optional owner filter."""
    where = "WHERE t.date LIKE ? AND t.category!=?"
    params: list = [f"{int(year):04d}-%", CATEGORY_TRANSFER]
    if owner:
        where += " AND a.owner=?"; params.append(owner)
    out = [{"month": m, "income": 0.0, "expenses": 0.0, "net": 0.0} for m in range(1, 13)]
    async with connect() as conn:
        cur = await conn.execute(
            f"""SELECT CAST(substr(t.date, 6, 2) AS INTEGER) m,
                       COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount END), 0),
                       COALESCE(SUM(CASE WHEN t.amount < 0 THEN -t.amount END), 0)
                FROM finance_transactions t JOIN finance_accounts a ON a.id = t.account_id
                {where}
                GROUP BY m""",
            params,
        )
        for m, inc, exp in await cur.fetchall():
            if 1 <= m <= 12:
                out[m - 1]["income"] = round(float(inc), 2)
                out[m - 1]["expenses"] = round(float(exp), 2)
                out[m - 1]["net"] = round(float(inc) - float(exp), 2)
    return out


async def category_spending_year(year: int, owner: str | None = None) -> list[dict]:
    """Expenses per category for the year: [{category, total, months:[12]}],
    sorted by total descending. Optional owner filter."""
    where = "WHERE t.amount < 0 AND t.date LIKE ? AND t.category!=?"
    params: list = [f"{int(year):04d}-%", CATEGORY_TRANSFER]
    if owner:
        where += " AND a.owner=?"; params.append(owner)
    agg: dict = {}
    async with connect() as conn:
        cur = await conn.execute(
            f"""SELECT t.category, CAST(substr(t.date, 6, 2) AS INTEGER) m,
                       SUM(-t.amount)
                FROM finance_transactions t JOIN finance_accounts a ON a.id = t.account_id
                {where}
                GROUP BY t.category, m""",
            params,
        )
        for cat, m, tot in await cur.fetchall():
            d = agg.setdefault(cat, {"category": cat, "total": 0.0, "months": [0.0] * 12})
            if 1 <= m <= 12:
                d["months"][m - 1] = round(float(tot), 2)
                d["total"] = round(d["total"] + float(tot), 2)
    return sorted(agg.values(), key=lambda x: x["total"], reverse=True)


async def years_with_data() -> list[int]:
    """Distinct years that have transactions (for historical navigation)."""
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT DISTINCT CAST(substr(date, 1, 4) AS INTEGER) y "
            "FROM finance_transactions ORDER BY y"
        )
        return [r[0] for r in await cur.fetchall()]


async def monthly_category_matrix(months: int | None = None) -> dict:
    """Expense matrix per category x month. Excludes internal transfers.
    months=None (default) -> the whole history (from the first movement to the
    current month). months=N -> only the last N months.
    Returns {"months": ["YYYY-MM", ...], "categories": {cat: [val...]}, "totals": [...]}.
    """
    today = date.today()
    if months is None:
        async with connect() as conn:
            cur = await conn.execute("SELECT MIN(substr(date,1,7)) FROM finance_transactions")
            first = (await cur.fetchone())[0]
        if first:
            fy, fm = int(first[:4]), int(first[5:7])
            months = (today.year - fy) * 12 + (today.month - fm) + 1
        else:
            months = 1
        months = max(1, min(months, 120))  # safety cap (10 years)
    labels = []
    y, m = today.year, today.month
    for _ in range(months):
        labels.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    labels.reverse()
    idx = {ym: i for i, ym in enumerate(labels)}
    cats: dict = {}
    totals = [0.0] * len(labels)
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT substr(date,1,7) ym, category, SUM(-amount) "
            "FROM finance_transactions "
            "WHERE amount<0 AND category!=? AND substr(date,1,7)>=? "
            "GROUP BY ym, category",
            (CATEGORY_TRANSFER, labels[0]),
        )
        for ym, cat, tot in await cur.fetchall():
            if ym not in idx:
                continue
            row = cats.setdefault(cat, [0.0] * len(labels))
            row[idx[ym]] = round(float(tot), 2)
            totals[idx[ym]] = round(totals[idx[ym]] + float(tot), 2)
    cats = dict(sorted(cats.items(), key=lambda kv: -sum(kv[1])))
    return {"months": labels, "categories": cats, "totals": totals}


async def recent_transactions(months: int | None = None) -> list[dict]:
    """Individual expense movements for drill-down (by category/month).
    months=None -> whole history; N -> last N months. Excludes transfers."""
    frm = "0000-00-00"
    if months is not None:
        today = date.today()
        y, m = today.year, today.month
        m -= (months - 1)
        while m <= 0:
            m += 12
            y -= 1
        frm = f"{y:04d}-{m:02d}-01"
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT date, -amount, category, description FROM finance_transactions "
            "WHERE amount<0 AND category!=? AND date>=? ORDER BY date DESC",
            (CATEGORY_TRANSFER, frm),
        )
        rows = await cur.fetchall()
    return [
        {"date": d, "amount": round(float(amt), 2), "category": cat,
         "description": (descr or "").strip()}
        for d, amt, cat, descr in rows
    ]
