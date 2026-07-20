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
from typing import Any

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


def build_set_clause(changes: dict[str, Any]) -> tuple[str, list]:
    """Turn a {column: value} dict into a SQL "col=?, col=?" clause and its params.

    This is the mechanical half shared by every "update only the fields the
    caller passed" function. Pairs whose value is None are dropped, so a caller
    can list every optional field and let the unset ones fall away. Returns
    ("", []) when nothing remains, which callers read as "no update to make".
    Coercion (float, strip, bool to 0/1, name to id) stays in the caller, so the
    helper never hides what is happening to the data.
    """
    present = {column: value for column, value in changes.items() if value is not None}
    clause = ", ".join(f"{column}=?" for column in present)
    return clause, list(present.values())


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
        await db.executescript(_FOOD_SCHEMA)
        await db.executescript(_UTILITIES_SCHEMA)
        await db.executescript(_CONVERSATION_SCHEMA)
        await db.executescript(_MISC_SCHEMA)
        await db.executescript(_IDENTITY_SCHEMA)
        await db.executescript(_LISTS_SCHEMA)
        await db.executescript(_EVENTS_SCHEMA)
        await _migrate(db)

        # Seed generic default categories (idempotent, no personal data).
        for cat in DEFAULT_CATEGORIES:
            await db.execute(
                "INSERT OR IGNORE INTO finance_categories (name) VALUES (?)", (cat,)
            )
        await db.commit()


async def _migrate(db) -> None:
    """Apply small additive migrations for databases created before a column existed.

    Only adds columns that ``CREATE TABLE IF NOT EXISTS`` cannot add to an
    existing table. Each step is guarded so it is safe to run on every startup.
    """
    await _add_column_if_missing(db, "list_items", "reminder_id", "INTEGER")


async def _add_column_if_missing(db, table: str, column: str, decl: str) -> None:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in await cursor.fetchall()}
    if column not in existing:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


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

# Nutrition columns are denormalized onto meals and meal_items so a day's
# totals are a single SUM. ``member`` identifies the family member (free text).
_FOOD_SCHEMA = """
CREATE TABLE IF NOT EXISTS diet_profiles (
    member TEXT PRIMARY KEY,
    sex TEXT,
    age INTEGER,
    height_cm REAL,
    weight_kg REAL,
    goal TEXT,
    activity_level TEXT,
    kcal_target INTEGER,
    bmi REAL,
    allergies TEXT,
    preferences TEXT,
    restrictions TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS weight_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member TEXT NOT NULL,
    weight_kg REAL NOT NULL,
    bmi REAL,
    logged_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member TEXT NOT NULL,
    meal_type TEXT NOT NULL,
    description TEXT NOT NULL,
    kcal_total REAL,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    fiber_g REAL,
    sugar_g REAL,
    sat_fat_g REAL,
    sodium_mg REAL,
    vit_c_mg REAL,
    vit_d_ug REAL,
    iron_mg REAL,
    calcium_mg REAL,
    potassium_mg REAL,
    magnesium_mg REAL,
    eaten_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    logged_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS meal_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meal_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    grams REAL,
    kcal REAL,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    fiber_g REAL,
    sugar_g REAL,
    sat_fat_g REAL,
    sodium_mg REAL,
    vit_c_mg REAL,
    vit_d_ug REAL,
    iron_mg REAL,
    calcium_mg REAL,
    potassium_mg REAL,
    magnesium_mg REAL
);
CREATE TABLE IF NOT EXISTS meal_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    meal_type TEXT NOT NULL,
    member TEXT NOT NULL DEFAULT '',
    items TEXT NOT NULL,
    recipe TEXT,
    servings INTEGER,
    kcal REAL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, meal_type, member)
);
CREATE TABLE IF NOT EXISTS hydration_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member TEXT NOT NULL,
    ml REAL NOT NULL,
    logged_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS shopping_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    qty TEXT,
    category TEXT,
    checked INTEGER DEFAULT 0,
    price REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS pantry_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    qty TEXT,
    category TEXT,
    expires_on TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS food_cache (
    key TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    source TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# One row per (utility, metric, year, month). metric: 'kwh'|'m3' for
# consumption, 'cost' for currency.
_UTILITIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS utility_bills (
    utility TEXT NOT NULL,
    metric TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    value REAL NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (utility, metric, year, month)
);
"""

# Raw conversation persistence (recent turns + rolling summary + key/value
# notes). This is NOT the semantic memory (that is laria.memory.MemoryBackend);
# it's the chat transcript the engine replays each turn.
_CONVERSATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS conv_summary (
    user_id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, key)
);
"""

# Reminders, news briefings, news blocklist, error log.
_MISC_SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    message TEXT NOT NULL,
    remind_at DATETIME,
    recurring TEXT,
    active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS briefings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    topics TEXT NOT NULL,
    cron TEXT NOT NULL,
    num_news INTEGER DEFAULT 5,
    active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS news_blocklist (
    user_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, domain)
);
CREATE TABLE IF NOT EXISTS error_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP,
    source TEXT,
    level TEXT,
    message TEXT NOT NULL,
    traceback TEXT
);
"""

# Identity: profiles (every household member, the data subject), users (optional
# login attached to a profile), and guardianships (a user acting for a dependent
# profile). See docs/design-auth.md.
_IDENTITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_dependent INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'adult',
    profile_id INTEGER REFERENCES profiles(id),
    telegram_chat_id TEXT UNIQUE,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS guardianships (
    guardian_user_id INTEGER NOT NULL REFERENCES users(id),
    profile_id INTEGER NOT NULL REFERENCES profiles(id),
    PRIMARY KEY (guardian_user_id, profile_id)
);
"""

# Generic household lists (todo/checklist/shopping/packing) and their items.
# An item's optional due_at (local-time string) is what a later step turns into
# a scheduled reminder. The food-specific shopping/pantry tables are separate.
_LISTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'todo',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS list_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id INTEGER NOT NULL REFERENCES lists(id),
    text TEXT NOT NULL,
    qty TEXT,
    checked INTEGER NOT NULL DEFAULT 0,
    due_at DATETIME,
    reminder_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_list_items_list_id ON list_items(list_id);
"""

_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    label TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'custom',
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    notify_days_before INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_events_active ON events(active);
"""
