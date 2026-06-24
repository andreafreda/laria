"""SQLite persistence foundation.

Replaces HARIA's ``memory/core.py`` DB bootstrap. Connection settings come from
``get_settings().db_path`` (no Supervisor, no hardcoded ``/config`` path). WAL +
busy_timeout keep concurrent writers (web API + channels + scheduler) from
hitting 'database is locked'.

Schema is split per domain; ``init_db`` runs every domain's DDL. Phase 1 ships
the finance domain; food/utilities/agent-conversation tables land as they are
ported.
"""
from __future__ import annotations

import os

import aiosqlite

from ..config import get_settings

# System category, excluded from reports; protected from rename/merge/delete.
CATEGORY_TRANSFER = "transfer"

# Generic seed categories (no personal data). Users can add/rename/merge.
DEFAULT_CATEGORIES: list[str] = [
    "groceries", "dining", "transport", "fuel", "utilities", "home",
    "health", "leisure", "shopping", "subscriptions", "education", "gifts",
    "taxes", "cash withdrawal", CATEGORY_TRANSFER, "salary", "other income",
]


def db_path() -> str:
    return get_settings().db_path


def connect() -> aiosqlite.Connection:
    """Open a connection to the configured DB (caller manages the context)."""
    return aiosqlite.connect(db_path())


async def init_db() -> None:
    """Create tables/indexes if missing and seed generic defaults. Idempotent."""
    path = db_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    async with aiosqlite.connect(path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.executescript(_FINANCE_SCHEMA)

        # Seed generic default categories (idempotent, no personal data).
        for cat in DEFAULT_CATEGORIES:
            await db.execute(
                "INSERT OR IGNORE INTO finance_categories (name) VALUES (?)", (cat,)
            )
        await db.commit()


_FINANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS finance_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    owner TEXT NOT NULL DEFAULT 'family',
    opening_balance REAL NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS finance_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES finance_accounts(id),
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    import_hash TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_finance_transactions_account_id
    ON finance_transactions(account_id);
CREATE TABLE IF NOT EXISTS finance_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS finance_budgets (
    category TEXT PRIMARY KEY,
    amount REAL NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS finance_rules (
    keyword TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS finance_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    target REAL NOT NULL,
    saved REAL NOT NULL DEFAULT 0,
    target_date TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""
