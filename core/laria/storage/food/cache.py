"""Nutrition lookup cache, remembered nutrition data for a food, by key.

Looking up a food's nutrition (via an external source or the LLM) is slow and
sometimes costly, so results are cached for a while. Entries older than the TTL
are treated as misses and cleaned up on the next write.
"""
from __future__ import annotations

import json

from ..db import connect

CACHE_TTL_DAYS = 90


async def get_food_cache(key: str) -> dict | None:
    """Return cached nutrition for ``key`` if present and still fresh, else None.

    The result carries a ``_source`` field noting where the data came from.
    Stale entries (older than the TTL) are ignored as if absent.
    """
    async with connect() as db:
        cur = await db.execute(
            "SELECT data, source FROM food_cache WHERE key = ? "
            "AND updated_at > datetime('now', ?)",
            (key.lower(), f"-{CACHE_TTL_DAYS} days"),
        )
        row = await cur.fetchone()
    if not row:
        return None
    cached = json.loads(row[0])
    cached["_source"] = row[1]
    return cached


async def set_food_cache(key: str, data: dict, source: str) -> None:
    """Cache nutrition data for a food, and sweep out entries past the TTL.

    ``source`` records provenance (which lookup produced it). Writing also prunes
    stale rows, so the cache self-maintains without a separate job.
    """
    async with connect() as db:
        await db.execute(
            """INSERT INTO food_cache (key, data, source, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE SET data=excluded.data,
                 source=excluded.source, updated_at=CURRENT_TIMESTAMP""",
            (key.lower(), json.dumps(data, ensure_ascii=False), source),
        )
        await db.execute(
            "DELETE FROM food_cache WHERE updated_at <= datetime('now', ?)",
            (f"-{CACHE_TTL_DAYS} days",),
        )
        await db.commit()
