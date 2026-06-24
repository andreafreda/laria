"""Spending categories — the labels every transaction is filed under.

Categories are free-form: the app seeds a generic set, and users add, rename or
merge them over time. One name is special: ``transfer`` marks money moving
between the household's own accounts, so it's protected from rename/merge/delete
and excluded from spending reports.
"""
from __future__ import annotations

from ..db import CATEGORY_TRANSFER, connect


async def list_categories() -> list[str]:
    """All category names, alphabetically — e.g. to populate a picker."""
    async with connect() as conn:
        cur = await conn.execute("SELECT name FROM finance_categories ORDER BY name")
        return [r[0] for r in await cur.fetchall()]


async def normalize_category(name: str) -> str:
    """Return the canonical stored spelling of a category, creating it if new.

    Matching is case-insensitive, so "Groceries" and "groceries" resolve to the
    same category instead of silently creating duplicates. Blank input falls
    back to "misc". Use this whenever you accept a category from free text.
    """
    raw = (name or "").strip()
    if not raw:
        raw = "misc"
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (raw,)
        )
        existing = await cur.fetchone()
        if existing:
            return existing[0]

        canonical = raw.lower()
        await conn.execute(
            "INSERT OR IGNORE INTO finance_categories (name) VALUES (?)", (canonical,)
        )
        await conn.commit()
        # Re-select so we return whatever spelling actually got stored, even if a
        # concurrent insert created a different variant in the meantime.
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (canonical,)
        )
        row = await cur.fetchone()
        return row[0] if row else canonical


async def delete_category(name: str) -> dict:
    """Delete a category, but only when nothing depends on it.

    Refuses if the category is the protected ``transfer`` one, or if any
    transaction or rule still uses it — move those first with rename/merge.
    Result shapes: ``{ok: True}`` / ``{ok: False, protected: True}`` /
    ``{ok: False, found: False}`` / ``{ok: False, in_use: True, transactions: N}`` /
    ``{ok: False, in_use_rules: True, rules: N}``.
    """
    name = (name or "").strip()
    if name.lower() == CATEGORY_TRANSFER:
        return {"ok": False, "protected": True}
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (name,)
        )
        row = await cur.fetchone()
        if not row:
            return {"ok": False, "found": False}
        canonical = row[0]

        cur = await conn.execute(
            "SELECT count(*) FROM finance_transactions WHERE category=?", (canonical,)
        )
        transaction_count = (await cur.fetchone())[0]
        if transaction_count > 0:
            return {"ok": False, "in_use": True, "transactions": transaction_count}

        cur = await conn.execute(
            "SELECT count(*) FROM finance_rules WHERE category=?", (canonical,)
        )
        rule_count = (await cur.fetchone())[0]
        if rule_count > 0:
            return {"ok": False, "in_use_rules": True, "rules": rule_count}

        await conn.execute("DELETE FROM finance_categories WHERE name=?", (canonical,))
        await conn.commit()
    return {"ok": True}


async def rename_category(old: str, new: str) -> bool:
    """Rename a category and move every transaction and rule onto the new name.

    If the new name already exists this becomes a merge into it. Returns False if
    the old category is missing or is the protected ``transfer`` category.
    """
    new = (new or "").strip().lower()
    if not new:
        return False
    if (old or "").strip().lower() == CATEGORY_TRANSFER:
        return False
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (old,)
        )
        row = await cur.fetchone()
        if not row:
            return False
        old_canonical = row[0]

        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (new,)
        )
        target_already_exists = await cur.fetchone()

        await conn.execute(
            "UPDATE finance_transactions SET category=? WHERE category=?", (new, old_canonical)
        )
        await conn.execute(
            "UPDATE finance_rules SET category=? WHERE category=?", (new, old_canonical)
        )
        if target_already_exists:
            await conn.execute("DELETE FROM finance_categories WHERE name=?", (old_canonical,))
        else:
            await conn.execute(
                "UPDATE finance_categories SET name=? WHERE name=?", (new, old_canonical)
            )
        await conn.commit()
        return True


async def merge_category(src: str, dst: str) -> bool:
    """Move everything from one category into another, then drop the source.

    ``dst`` is created if it doesn't exist. Returns False if the source is
    missing, is the protected ``transfer`` category, or equals the destination.
    """
    if (src or "").strip().lower() == CATEGORY_TRANSFER:
        return False
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (src,)
        )
        src_row = await cur.fetchone()
        if not src_row:
            return False
        src_canonical = src_row[0]

        dst_canonical = (dst or "").strip().lower()
        if not dst_canonical or dst_canonical == src_canonical.lower():
            return False

        await conn.execute(
            "INSERT OR IGNORE INTO finance_categories (name) VALUES (?)", (dst_canonical,)
        )
        cur = await conn.execute(
            "SELECT name FROM finance_categories WHERE lower(name)=lower(?)", (dst_canonical,)
        )
        dst_canonical = (await cur.fetchone())[0]

        await conn.execute(
            "UPDATE finance_transactions SET category=? WHERE category=?", (dst_canonical, src_canonical)
        )
        await conn.execute(
            "UPDATE finance_rules SET category=? WHERE category=?", (dst_canonical, src_canonical)
        )
        await conn.execute("DELETE FROM finance_categories WHERE name=?", (src_canonical,))
        await conn.commit()
        return True
