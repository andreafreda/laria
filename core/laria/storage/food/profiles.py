"""Diet profiles, one stored health/nutrition profile per family member.

``member`` is a free-text identifier (no hardcoded members). A profile holds the
slow-changing facts used to tailor advice and targets: sex, age, height, goal,
calorie target, allergies and preferences.
"""
from __future__ import annotations

from ..db import connect

_PROFILE_FIELDS = (
    "member", "sex", "age", "height_cm", "weight_kg", "goal",
    "activity_level", "kcal_target", "bmi", "allergies", "preferences", "restrictions",
)


def _profile_row(row) -> dict:
    """Map a full profile DB row to a dict keyed by field name."""
    return dict(zip(_PROFILE_FIELDS, row))


async def get_profile(member: str) -> dict | None:
    """The full diet profile for a member, or None if they have none yet."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT member, sex, age, height_cm, weight_kg, goal, activity_level,
                      kcal_target, bmi, allergies, preferences, restrictions
               FROM diet_profiles WHERE member = ?""",
            (member,),
        )
        row = await cur.fetchone()
    return _profile_row(row) if row else None


async def delete_profile(member: str) -> bool:
    """Delete a member's diet profile. Returns False if they had none."""
    async with connect() as db:
        cur = await db.execute("DELETE FROM diet_profiles WHERE member = ?", (member,))
        await db.commit()
        return cur.rowcount > 0


async def upsert_profile(member: str, fields: dict) -> None:
    """Create or patch a member's profile, touching only the fields you pass.

    Unknown keys are ignored, so you can hand it a loose dict. On an existing
    profile this is a partial update; on a new member it inserts a fresh row.
    """
    columns = [name for name in fields if name in _PROFILE_FIELDS and name != "member"]
    async with connect() as db:
        already_exists = await (await db.execute(
            "SELECT 1 FROM diet_profiles WHERE member = ?", (member,)
        )).fetchone()
        if already_exists:
            if columns:
                assignments = ", ".join(f"{c} = ?" for c in columns) + ", updated_at = CURRENT_TIMESTAMP"
                await db.execute(
                    f"UPDATE diet_profiles SET {assignments} WHERE member = ?",
                    [fields[c] for c in columns] + [member],
                )
        else:
            insert_columns = ["member"] + columns
            placeholders = ", ".join("?" for _ in insert_columns)
            await db.execute(
                f"INSERT INTO diet_profiles ({', '.join(insert_columns)}) VALUES ({placeholders})",
                [member] + [fields[c] for c in columns],
            )
        await db.commit()


async def list_profiles() -> list[dict]:
    """Every member's profile (core fields only), for an overview screen."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT member, sex, age, height_cm, weight_kg, goal, activity_level,
                      kcal_target, bmi FROM diet_profiles ORDER BY member"""
        )
        rows = await cur.fetchall()
    columns = ("member", "sex", "age", "height_cm", "weight_kg", "goal",
               "activity_level", "kcal_target", "bmi")
    return [dict(zip(columns, r)) for r in rows]
