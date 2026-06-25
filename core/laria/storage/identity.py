"""Identity storage: profiles, users and guardianships.

The data model (see docs/design-auth.md):
  - a profile is a household member, the subject of the data; it always exists
  - a user is an optional login attached to a profile
  - a guardianship lets a user act for a dependent profile (parent for child)

This module is plain CRUD; the login flow and bootstrap live in the auth service.
"""
from __future__ import annotations

from .db import connect


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #

def _profile(row) -> dict:
    return {"id": row[0], "name": row[1], "is_dependent": bool(row[2])}


async def create_profile(name: str, is_dependent: bool = False) -> int:
    """Create a household member profile (idempotent on name); return its id."""
    async with connect() as db:
        await db.execute(
            "INSERT OR IGNORE INTO profiles (name, is_dependent) VALUES (?, ?)",
            (name.strip(), 1 if is_dependent else 0),
        )
        await db.commit()
        cur = await db.execute("SELECT id FROM profiles WHERE name=?", (name.strip(),))
        return (await cur.fetchone())[0]


async def get_profile(name: str) -> dict | None:
    async with connect() as db:
        cur = await db.execute(
            "SELECT id, name, is_dependent FROM profiles WHERE name=?", (name.strip(),))
        row = await cur.fetchone()
    return _profile(row) if row else None


async def list_profiles() -> list[dict]:
    async with connect() as db:
        cur = await db.execute(
            "SELECT id, name, is_dependent FROM profiles ORDER BY name")
        return [_profile(r) for r in await cur.fetchall()]


# --------------------------------------------------------------------------- #
# Users (logins)
# --------------------------------------------------------------------------- #

def _user(row) -> dict:
    return {"id": row[0], "username": row[1], "password_hash": row[2],
            "role": row[3], "profile_id": row[4], "telegram_chat_id": row[5],
            "must_change_password": bool(row[6])}


_USER_COLUMNS = ("id, username, password_hash, role, profile_id, "
                 "telegram_chat_id, must_change_password")


async def create_user(username: str, password_hash: str, *, role: str = "adult",
                      profile_id: int | None = None,
                      telegram_chat_id: str | None = None) -> int:
    """Create a login. Returns the new user id.

    A password hash is stored, never a plaintext password (hash it with
    laria.security first). ``profile_id`` links the login to the member it
    represents.
    """
    async with connect() as db:
        cur = await db.execute(
            """INSERT INTO users (username, password_hash, role, profile_id, telegram_chat_id)
               VALUES (?, ?, ?, ?, ?)""",
            (username.strip(), password_hash, role, profile_id, telegram_chat_id),
        )
        await db.commit()
        return cur.lastrowid


async def get_user_by_username(username: str) -> dict | None:
    return await _get_user("username=?", (username.strip(),))


async def get_user_by_id(user_id: int) -> dict | None:
    return await _get_user("id=?", (int(user_id),))


async def get_user_by_telegram(chat_id: str) -> dict | None:
    """The user linked to a Telegram chat id, or None (for the channel allowlist)."""
    return await _get_user("telegram_chat_id=?", (str(chat_id),))


async def _get_user(where: str, params: tuple) -> dict | None:
    async with connect() as db:
        cur = await db.execute(f"SELECT {_USER_COLUMNS} FROM users WHERE {where}", params)
        row = await cur.fetchone()
    return _user(row) if row else None


async def list_users() -> list[dict]:
    async with connect() as db:
        cur = await db.execute(f"SELECT {_USER_COLUMNS} FROM users ORDER BY username")
        return [_user(r) for r in await cur.fetchall()]


async def set_password(user_id: int, password_hash: str, *,
                       must_change: bool = False) -> bool:
    """Replace a user's password hash. Set ``must_change`` for a temporary one
    that forces a change at next login."""
    async with connect() as db:
        cur = await db.execute(
            "UPDATE users SET password_hash=?, must_change_password=? WHERE id=?",
            (password_hash, 1 if must_change else 0, int(user_id)),
        )
        await db.commit()
        return cur.rowcount > 0


async def link_telegram(user_id: int, chat_id: str) -> bool:
    """Bind a verified Telegram chat id to a user (enables Telegram and reset)."""
    async with connect() as db:
        cur = await db.execute(
            "UPDATE users SET telegram_chat_id=? WHERE id=?", (str(chat_id), int(user_id)))
        await db.commit()
        return cur.rowcount > 0


async def count_users() -> int:
    """How many logins exist (used to decide first-run owner bootstrap)."""
    async with connect() as db:
        cur = await db.execute("SELECT count(*) FROM users")
        return (await cur.fetchone())[0]


# --------------------------------------------------------------------------- #
# Guardianships
# --------------------------------------------------------------------------- #

async def add_guardianship(guardian_user_id: int, profile_id: int) -> None:
    """Let a user act for a dependent profile (idempotent)."""
    async with connect() as db:
        await db.execute(
            "INSERT OR IGNORE INTO guardianships (guardian_user_id, profile_id) VALUES (?, ?)",
            (int(guardian_user_id), int(profile_id)),
        )
        await db.commit()


async def list_wards(guardian_user_id: int) -> list[int]:
    """Profile ids a user is guardian of."""
    async with connect() as db:
        cur = await db.execute(
            "SELECT profile_id FROM guardianships WHERE guardian_user_id=?",
            (int(guardian_user_id),))
        return [r[0] for r in await cur.fetchall()]


async def is_guardian(guardian_user_id: int, profile_id: int) -> bool:
    """Whether a user may act for a given profile."""
    async with connect() as db:
        cur = await db.execute(
            "SELECT 1 FROM guardianships WHERE guardian_user_id=? AND profile_id=?",
            (int(guardian_user_id), int(profile_id)))
        return (await cur.fetchone()) is not None
