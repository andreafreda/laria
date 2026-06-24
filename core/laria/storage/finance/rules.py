"""Auto-categorization rules, keyword to category.

When a transaction's description contains a rule's keyword, the transaction is
filed under that rule's category. This is what lets imported bank statements get
sensible categories without manual tagging. Rules are matched longest-keyword
first, so a specific rule wins over a generic one.
"""
from __future__ import annotations

import collections

from ..db import connect

MIN_KEYWORD_LENGTH = 3  # shorter keywords match too much to be useful


async def add_rule(keyword: str, category: str) -> str:
    """Create or update a rule mapping ``keyword`` to ``category``.

    Both are stored lowercase (matching is case-insensitive). The category is
    created if new. Raises ValueError if either is empty or the keyword is too
    short to be a meaningful match. Returns the canonical category.
    """
    keyword = (keyword or "").strip().lower()
    category = (category or "").strip().lower()
    if not keyword or not category:
        raise ValueError("keyword and category are required")
    if len(keyword) < MIN_KEYWORD_LENGTH:
        raise ValueError(f"keyword too short: minimum {MIN_KEYWORD_LENGTH} characters")
    async with connect() as conn:
        await conn.execute("INSERT OR IGNORE INTO finance_categories (name) VALUES (?)", (category,))
        await conn.execute(
            "INSERT INTO finance_rules (keyword, category) VALUES (?, ?) "
            "ON CONFLICT(keyword) DO UPDATE SET category=excluded.category",
            (keyword, category),
        )
        await conn.commit()
    return category


async def delete_rule(keyword: str) -> bool:
    """Remove a rule by its keyword. Returns False if there was no such rule."""
    async with connect() as conn:
        cur = await conn.execute(
            "DELETE FROM finance_rules WHERE keyword=?", ((keyword or "").strip().lower(),)
        )
        await conn.commit()
        return cur.rowcount > 0


async def list_rules() -> list[dict]:
    """All rules, longest keyword first so the most specific one matches first."""
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT keyword, category FROM finance_rules ORDER BY length(keyword) DESC"
        )
        return [{"keyword": r[0], "category": r[1]} for r in await cur.fetchall()]


def match_rule(description: str, rules: list[dict]) -> str | None:
    """Return the category for the first rule whose keyword is in ``description``.

    ``rules`` must already be ordered longest-keyword-first (as ``list_rules``
    returns them) so the most specific rule wins. Returns None if nothing matches.
    Pass the rules in rather than fetching here, so callers can match many
    transactions against a single fetch.
    """
    text = (description or "").lower()
    for rule in rules:
        if rule["keyword"] in text:
            return rule["category"]
    return None


async def apply_rules() -> dict:
    """Re-apply every rule to every existing transaction (a full re-tag).

    Use this after editing rules to bring old transactions in line. Returns a
    count of how many transactions moved into each category. Note this overrides
    manual categorizations too, for a gentler pass use ``apply_rule``.
    """
    rules = await list_rules()
    if not rules:
        return {}
    moved_per_category = collections.Counter()
    async with connect() as conn:
        cur = await conn.execute("SELECT id, description, category FROM finance_transactions")
        rows = await cur.fetchall()
        for transaction_id, description, current_category in rows:
            new_category = match_rule(description, rules)
            if new_category and new_category != current_category:
                await conn.execute(
                    "UPDATE finance_transactions SET category=? WHERE id=?",
                    (new_category, transaction_id),
                )
                moved_per_category[new_category] += 1
        await conn.commit()
    return dict(moved_per_category)


async def apply_rule(keyword: str) -> int:
    """Apply a single rule to existing transactions; return how many it moved.

    Unlike ``apply_rules`` this only touches transactions not already in the
    rule's category, so manual categorizations on other categories are left
    alone. Handy right after adding one new rule.
    """
    keyword = (keyword or "").strip().lower()
    async with connect() as conn:
        cur = await conn.execute(
            "SELECT category FROM finance_rules WHERE keyword=?", (keyword,)
        )
        row = await cur.fetchone()
        if not row:
            return 0
        category = row[0]
        cur = await conn.execute(
            "UPDATE finance_transactions SET category=? "
            "WHERE category!=? AND instr(lower(description), ?) > 0",
            (category, category, keyword),
        )
        await conn.commit()
        return cur.rowcount
