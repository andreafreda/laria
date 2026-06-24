"""Conversation persistence: recent turns, rolling summary, key/value notes.
Ported from HARIA ``memory/core.py`` (the chat-transcript parts).

This is the raw transcript the engine replays each turn, distinct from the
semantic agent memory (``laria.memory.MemoryBackend``). HARIA's FTS keyword
recall is intentionally dropped here: semantic/keyword recall now belongs to the
MemoryBackend.
"""
from __future__ import annotations

from .db import connect

MAX_HISTORY = 10      # raw turns replayed per request
SUMMARY_BATCH = 20    # old turns folded into the summary per pass


# --------------------------------------------------------------------------- #
# Recent history
# --------------------------------------------------------------------------- #

async def get_history(user_id: str) -> list[dict]:
    async with connect() as db:
        cur = await db.execute(
            """SELECT role, content FROM conversations
               WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
            (user_id, MAX_HISTORY),
        )
        rows = await cur.fetchall()
    return [{"role": r, "content": c} for r, c in reversed(rows)]


async def save_turn(user_id: str, role: str, content: str) -> None:
    async with connect() as db:
        await db.execute(
            "INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )
        await db.commit()


async def clear_history(user_id: str) -> None:
    """Delete the user's raw history + summary."""
    async with connect() as db:
        await db.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM conv_summary WHERE user_id = ?", (user_id,))
        await db.commit()


async def count_history(user_id: str) -> int:
    async with connect() as db:
        cur = await db.execute(
            "SELECT count(*) FROM conversations WHERE user_id = ?", (user_id,)
        )
        return (await cur.fetchone())[0]


# --------------------------------------------------------------------------- #
# Long-term summary
# --------------------------------------------------------------------------- #

async def get_summary(user_id: str) -> str | None:
    async with connect() as db:
        cur = await db.execute(
            "SELECT summary FROM conv_summary WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def set_summary(user_id: str, summary: str) -> None:
    async with connect() as db:
        await db.execute(
            """INSERT INTO conv_summary (user_id, summary, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   summary=excluded.summary, updated_at=CURRENT_TIMESTAMP""",
            (user_id, summary),
        )
        await db.commit()


async def get_old_turns(user_id: str, keep: int = MAX_HISTORY,
                        batch: int = SUMMARY_BATCH) -> list[dict]:
    """Turns older than the recent ``keep`` window, oldest first (max ``batch``).
    Empty if there is nothing to summarize."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT id, role, content FROM conversations
               WHERE user_id = ? AND id NOT IN (
                   SELECT id FROM conversations WHERE user_id = ?
                   ORDER BY id DESC LIMIT ?
               )
               ORDER BY id ASC LIMIT ?""",
            (user_id, user_id, keep, batch),
        )
        rows = await cur.fetchall()
    return [{"id": i, "role": r, "content": c} for i, r, c in rows]


async def delete_turns(ids: list[int]) -> None:
    if not ids:
        return
    async with connect() as db:
        await db.executemany(
            "DELETE FROM conversations WHERE id = ?", [(i,) for i in ids]
        )
        await db.commit()


# --------------------------------------------------------------------------- #
# Key/value notes
# --------------------------------------------------------------------------- #

async def get_notes(user_id: str) -> dict[str, str]:
    async with connect() as db:
        cur = await db.execute(
            "SELECT key, value FROM notes WHERE user_id = ?", (user_id,)
        )
        rows = await cur.fetchall()
    return {k: v for k, v in rows}


async def save_note(user_id: str, key: str, value: str) -> None:
    async with connect() as db:
        await db.execute(
            """INSERT INTO notes (user_id, key, value, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id, key) DO UPDATE SET
                   value=excluded.value, updated_at=CURRENT_TIMESTAMP""",
            (user_id, key, value),
        )
        await db.commit()
