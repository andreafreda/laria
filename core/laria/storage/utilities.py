"""Utilities storage: utility bills (consumption/cost per month). Ported from
HARIA ``memory/bollette.py``.

One row per (utility, metric, year, month). metric: 'kwh'|'m3' for consumption,
'cost' for currency.
"""
from __future__ import annotations

from .db import connect


async def set_bill(utility: str, metric: str, year: int, month: int, value: float) -> None:
    """Upsert a single month."""
    async with connect() as db:
        await db.execute(
            """INSERT INTO utility_bills (utility, metric, year, month, value, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(utility, metric, year, month)
               DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP""",
            (utility, metric, int(year), int(month), float(value)),
        )
        await db.commit()


async def set_bill_range(utility: str, metric: str, year: int,
                         m_start: int, m_end: int, total: float) -> None:
    """Spread ``total`` evenly over months [m_start, m_end] (1-based). The last
    month absorbs the rounding remainder so the months sum back to ``total``."""
    m_start, m_end = int(m_start), int(m_end)
    if m_end < m_start:
        m_end = m_start
    n = m_end - m_start + 1
    per = round(float(total) / n, 1)
    last_val = round(float(total) - per * (n - 1), 1)
    async with connect() as db:
        for mth in range(m_start, m_end + 1):
            value = last_val if mth == m_end else per
            await db.execute(
                """INSERT INTO utility_bills (utility, metric, year, month, value, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(utility, metric, year, month)
                   DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP""",
                (utility, metric, int(year), mth, value),
            )
        await db.commit()


def _fmt_num(v: float) -> str:
    """Integer without decimals if whole, else compact decimal form."""
    return str(int(v)) if float(v).is_integer() else str(v)


async def get_bill_csv(utility: str, metric: str, year: int) -> str:
    """Return the 12 monthly values as CSV (0 for missing months)."""
    vals = [0.0] * 12
    async with connect() as db:
        cur = await db.execute(
            "SELECT month, value FROM utility_bills WHERE utility=? AND metric=? AND year=?",
            (utility, metric, int(year)),
        )
        for mth, val in await cur.fetchall():
            if 1 <= mth <= 12:
                vals[mth - 1] = val
    return ",".join(_fmt_num(v) for v in vals)


async def get_bill_existing_range(utility: str, metric: str, year: int,
                                  m_start: int, m_end: int) -> list[tuple]:
    """Months already valued (!=0) in range [m_start, m_end]. [(month, value)]."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT month, value FROM utility_bills
               WHERE utility=? AND metric=? AND year=? AND month>=? AND month<=? AND value!=0
               ORDER BY month""",
            (utility, metric, int(year), int(m_start), int(m_end)),
        )
        return [(r[0], r[1]) for r in await cur.fetchall()]


async def get_bill_years(utility: str, metric: str) -> list[int]:
    """Years with at least one value for (utility, metric)."""
    async with connect() as db:
        cur = await db.execute(
            "SELECT DISTINCT year FROM utility_bills WHERE utility=? AND metric=? ORDER BY year",
            (utility, metric),
        )
        return [r[0] for r in await cur.fetchall()]


async def list_bill_series() -> list[tuple[str, str]]:
    """Distinct (utility, metric) pairs present in the data.

    Drives the MQTT compat publisher: one sensor series per pair, spread across
    its years. Ordered so the published set is stable between runs.
    """
    async with connect() as db:
        cur = await db.execute(
            "SELECT DISTINCT utility, metric FROM utility_bills ORDER BY utility, metric"
        )
        return [(r[0], r[1]) for r in await cur.fetchall()]


async def bills_empty() -> bool:
    async with connect() as db:
        cur = await db.execute("SELECT 1 FROM utility_bills LIMIT 1")
        return (await cur.fetchone()) is None


async def seed_bills(rows: list[tuple]) -> None:
    """Bulk initial insert. rows = [(utility, metric, year, month, value), ...]."""
    if not rows:
        return
    async with connect() as db:
        await db.executemany(
            """INSERT INTO utility_bills (utility, metric, year, month, value)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(utility, metric, year, month) DO UPDATE SET value=excluded.value""",
            rows,
        )
        await db.commit()
