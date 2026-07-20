"""Migrate a HARIA SQLite database into a LARIA one.

HARIA and LARIA share most table shapes (LARIA was ported from HARIA), so most
of this is a straight copy. The exception is finance: HARIA's Italian econ_*
tables map to LARIA's English finance_* tables, column by column. Reminders and
briefings are re-owned to the LARIA owner, since HARIA keyed them by Telegram
chat id while LARIA keys them by user id.

Usage:
    python tools/migrate_haria.py --source haria.db --target laria.db [--owner-id N]

The target keeps whatever it already has (its owner, login, settings); this only
adds the HARIA data. Run it against a copy first and check the printed counts.
"""
from __future__ import annotations

import argparse
import sqlite3


def _owner_id(target: sqlite3.Connection, explicit: int | None) -> int:
    """The LARIA user id to attribute reminders/briefings to."""
    if explicit is not None:
        return explicit
    row = target.execute(
        "SELECT id FROM users WHERE role = 'owner' ORDER BY id LIMIT 1").fetchone()
    return row[0] if row else 1


def _copy(source, target, select_sql, insert_sql, transform=None) -> int:
    """Read rows from source, optionally transform, insert into target; count them."""
    rows = source.execute(select_sql).fetchall()
    count = 0
    for row in rows:
        values = transform(row) if transform else tuple(row)
        target.execute(insert_sql, values)
        count += 1
    return count


def migrate(source_path: str, target_path: str, owner_id: int | None = None) -> dict:
    """Copy HARIA data into the LARIA database; return a per-table count."""
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(target_path)
    target.execute("PRAGMA foreign_keys = OFF")
    owner = _owner_id(target, owner_id)
    counts: dict[str, int] = {}

    # --- finance: econ_* (Italian) -> finance_* (English) ---
    # Accounts first so transactions' account_id references resolve; ids are
    # preserved because a fresh LARIA finance store has none to collide with.
    counts["finance_accounts"] = _copy(
        source, target,
        "SELECT id, nome, tipo, saldo_iniziale, attivo, created_at, intestatario FROM econ_conti",
        """INSERT INTO finance_accounts (id, name, type, opening_balance, active, created_at, owner)
           VALUES (?, ?, ?, ?, ?, ?, ?)""")

    counts["finance_transactions"] = _copy(
        source, target,
        """SELECT id, conto_id, data, importo, categoria, descrizione, import_hash, created_at
           FROM econ_transazioni""",
        """INSERT INTO finance_transactions
           (id, account_id, date, amount, category, description, import_hash, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""")

    # Categories match on name (transactions store the category text, not an id),
    # so ignore collisions with LARIA's seeded defaults.
    counts["finance_categories"] = _copy(
        source, target,
        "SELECT nome FROM econ_categorie",
        "INSERT OR IGNORE INTO finance_categories (name) VALUES (?)")

    counts["finance_budgets"] = _copy(
        source, target,
        "SELECT categoria, importo, updated_at FROM econ_budget",
        """INSERT OR REPLACE INTO finance_budgets (category, amount, updated_at)
           VALUES (?, ?, ?)""")

    counts["finance_goals"] = _copy(
        source, target,
        "SELECT id, nome, target, accantonato, target_date, created_at FROM econ_obiettivi",
        """INSERT INTO finance_goals (id, name, target, saved, target_date, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""")

    counts["finance_rules"] = _copy(
        source, target,
        "SELECT keyword, categoria, created_at FROM econ_regole",
        "INSERT OR IGNORE INTO finance_rules (keyword, category, created_at) VALUES (?, ?, ?)")

    # --- utilities: bollette -> utility_bills (same columns) ---
    counts["utility_bills"] = _copy(
        source, target,
        "SELECT utility, metric, year, month, value, updated_at FROM bollette",
        """INSERT OR REPLACE INTO utility_bills (utility, metric, year, month, value, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""")

    # --- food: identical table shapes, direct copy ---
    counts["diet_profiles"] = _copy_same(source, target, "diet_profiles", replace=True)
    counts["meals"] = _copy_same(source, target, "meals")
    counts["meal_items"] = _copy_same(source, target, "meal_items")
    counts["meal_plan"] = _copy_same(source, target, "meal_plan")
    counts["hydration_log"] = _copy_same(source, target, "hydration_log")
    counts["weight_log"] = _copy_same(source, target, "weight_log")
    counts["shopping_items"] = _copy_same(source, target, "shopping_items")
    counts["pantry_items"] = _copy_same(source, target, "pantry_items")

    # --- reminders and briefings: re-owned to the LARIA owner ---
    counts["reminders"] = _copy(
        source, target,
        "SELECT message, remind_at, recurring, active FROM reminders WHERE active = 1",
        """INSERT INTO reminders (user_id, message, remind_at, recurring, active)
           VALUES (?, ?, ?, ?, ?)""",
        transform=lambda r: (str(owner), r[0], r[1], r[2], r[3]))

    counts["briefings"] = _copy(
        source, target,
        "SELECT topics, cron, num_news, active FROM briefings WHERE active = 1",
        """INSERT INTO briefings (user_id, topics, cron, num_news, active)
           VALUES (?, ?, ?, ?, ?)""",
        transform=lambda r: (str(owner), r[0], r[1], r[2], r[3]))

    target.commit()
    source.close()
    target.close()
    return counts


def _copy_same(source, target, table, replace=False) -> int:
    """Copy a table that has identical columns in both databases."""
    columns = [row[1] for row in source.execute(f"PRAGMA table_info({table})")]
    placeholders = ", ".join("?" for _ in columns)
    verb = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
    insert_sql = f"{verb} INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    return _copy(source, target, f"SELECT {', '.join(columns)} FROM {table}", insert_sql)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate HARIA data into LARIA.")
    parser.add_argument("--source", required=True, help="HARIA sqlite file")
    parser.add_argument("--target", required=True, help="LARIA sqlite file (modified in place)")
    parser.add_argument("--owner-id", type=int, default=None,
                        help="LARIA user id for reminders/briefings (default: the owner)")
    args = parser.parse_args()

    counts = migrate(args.source, args.target, args.owner_id)
    print("Migrated rows:")
    for table, count in counts.items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
