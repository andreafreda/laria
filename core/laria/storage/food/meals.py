"""Logged meals, what each member actually ate, with nutrition totals.

A meal carries denormalized macro/micro totals plus its individual food items
(``meal_items``), so a day's nutrition is one SUM. This module also answers the
"what did we eat" questions: per-day totals, logged days, CSV export.
"""
from __future__ import annotations

from ..db import build_set_clause, connect


async def add_meal(member: str, meal_type: str, description: str, totals: dict,
                   items: list[dict], eaten_at: str | None, logged_by: str | None) -> dict:
    """Record a meal and its food items in one go; return the new meal id.

    ``totals`` and each item carry the same nutrition keys (kcal/macros/micros);
    missing ones are stored as NULL. ``eaten_at`` defaults to now when omitted.
    """
    async with connect() as db:
        cur = await db.execute(
            """INSERT INTO meals
               (member, meal_type, description, kcal_total, protein_g, carbs_g, fat_g,
                fiber_g, sugar_g, sat_fat_g, sodium_mg,
                vit_c_mg, vit_d_ug, iron_mg, calcium_mg, potassium_mg, magnesium_mg,
                eaten_at, logged_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)""",
            (member, meal_type, description,
             totals.get("kcal_total"), totals.get("protein_g"),
             totals.get("carbs_g"), totals.get("fat_g"),
             totals.get("fiber_g"), totals.get("sugar_g"),
             totals.get("sat_fat_g"), totals.get("sodium_mg"),
             totals.get("vit_c_mg"), totals.get("vit_d_ug"), totals.get("iron_mg"),
             totals.get("calcium_mg"), totals.get("potassium_mg"), totals.get("magnesium_mg"),
             eaten_at, logged_by),
        )
        meal_id = cur.lastrowid
        for item in items or []:
            await db.execute(
                """INSERT INTO meal_items
                   (meal_id, name, grams, kcal, protein_g, carbs_g, fat_g,
                    fiber_g, sugar_g, sat_fat_g, sodium_mg,
                    vit_c_mg, vit_d_ug, iron_mg, calcium_mg, potassium_mg, magnesium_mg)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (meal_id, item.get("name"), item.get("grams"), item.get("kcal"),
                 item.get("protein_g"), item.get("carbs_g"), item.get("fat_g"),
                 item.get("fiber_g"), item.get("sugar_g"),
                 item.get("sat_fat_g"), item.get("sodium_mg"),
                 item.get("vit_c_mg"), item.get("vit_d_ug"), item.get("iron_mg"),
                 item.get("calcium_mg"), item.get("potassium_mg"), item.get("magnesium_mg")),
            )
        await db.commit()
    return {"id": meal_id, "member": member, "meal_type": meal_type}


async def update_meal(meal_id: int, meal_type: str | None = None, description: str | None = None,
                      totals: dict | None = None, eaten_at: str | None = None) -> bool:
    """Edit a logged meal, changing only the fields you pass.

    Only the headline totals (kcal, protein, carbs, fat) are updatable here; the
    detailed item rows aren't rewritten. Returns False if nothing changed.
    """
    totals = totals or {}
    changes = {
        "meal_type": meal_type,
        "description": description,
        "eaten_at": eaten_at,
        "kcal_total": totals.get("kcal_total"),
        "protein_g": totals.get("protein_g"),
        "carbs_g": totals.get("carbs_g"),
        "fat_g": totals.get("fat_g"),
    }
    clause, params = build_set_clause(changes)
    if not clause:
        return False
    params.append(int(meal_id))
    async with connect() as db:
        cur = await db.execute(f"UPDATE meals SET {clause} WHERE id = ?", params)
        await db.commit()
        return cur.rowcount > 0


async def delete_meal(meal_id: int) -> bool:
    """Delete a logged meal and its food items. Returns False if it didn't exist."""
    async with connect() as db:
        await db.execute("DELETE FROM meal_items WHERE meal_id = ?", (int(meal_id),))
        cur = await db.execute("DELETE FROM meals WHERE id = ?", (int(meal_id),))
        await db.commit()
        return cur.rowcount > 0


async def get_meals(member: str, date_from: str | None = None,
                    date_to: str | None = None) -> list[dict]:
    """A member's meals (newest first, up to 50), optionally within a date range."""
    query = ("SELECT id, meal_type, description, kcal_total, protein_g, carbs_g, fat_g, eaten_at "
             "FROM meals WHERE member = ?")
    params: list = [member]
    if date_from:
        query += " AND DATE(eaten_at) >= DATE(?)"; params.append(date_from)
    if date_to:
        query += " AND DATE(eaten_at) <= DATE(?)"; params.append(date_to)
    query += " ORDER BY eaten_at DESC LIMIT 50"
    async with connect() as db:
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
    return [
        {"id": r[0], "meal_type": r[1], "description": r[2], "kcal_total": r[3],
         "protein_g": r[4], "carbs_g": r[5], "fat_g": r[6], "eaten_at": r[7]}
        for r in rows
    ]


async def get_logged_days(days_back: int = 30) -> list[dict]:
    """Recent days that have any logged meals, newest first.

    Each entry is ``{day, members, meals, kcal}``, handy for a "logging streak"
    or activity calendar over the last ``days_back`` days.
    """
    async with connect() as db:
        cur = await db.execute(
            """SELECT DATE(eaten_at) AS day,
                      COUNT(DISTINCT member) AS members,
                      COUNT(*) AS meals,
                      COALESCE(SUM(kcal_total), 0) AS kcal
               FROM meals
               WHERE DATE(eaten_at) >= DATE('now', ?)
               GROUP BY day ORDER BY day DESC""",
            (f"-{int(days_back)} days",),
        )
        rows = await cur.fetchall()
    return [{"day": r[0], "members": r[1], "meals": r[2], "kcal": round(r[3], 1)} for r in rows]


async def get_day_totals(member: str, day: str) -> dict:
    """Sum a member's nutrition for one day (YYYY-MM-DD): kcal, macros, micros.

    Always returns the full set of nutrient keys (zeros when nothing is logged)
    so callers can render a complete breakdown without missing-key checks.
    """
    async with connect() as db:
        cur = await db.execute(
            """SELECT COALESCE(SUM(kcal_total),0), COALESCE(SUM(protein_g),0),
                      COALESCE(SUM(carbs_g),0), COALESCE(SUM(fat_g),0),
                      COALESCE(SUM(fiber_g),0), COALESCE(SUM(sugar_g),0),
                      COALESCE(SUM(sat_fat_g),0), COALESCE(SUM(sodium_mg),0),
                      COALESCE(SUM(vit_c_mg),0), COALESCE(SUM(vit_d_ug),0),
                      COALESCE(SUM(iron_mg),0), COALESCE(SUM(calcium_mg),0),
                      COALESCE(SUM(potassium_mg),0), COALESCE(SUM(magnesium_mg),0), COUNT(*)
               FROM meals WHERE member = ? AND DATE(eaten_at) = ?""",
            (member, day),
        )
        r = await cur.fetchone()
    return {"kcal": round(r[0], 1), "protein_g": round(r[1], 1),
            "carbs_g": round(r[2], 1), "fat_g": round(r[3], 1),
            "fiber_g": round(r[4], 1), "sugar_g": round(r[5], 1),
            "sat_fat_g": round(r[6], 1), "sodium_mg": round(r[7], 1),
            "vit_c_mg": round(r[8], 1), "vit_d_ug": round(r[9], 1),
            "iron_mg": round(r[10], 1), "calcium_mg": round(r[11], 1),
            "potassium_mg": round(r[12], 1), "magnesium_mg": round(r[13], 1), "meals": r[14]}


async def export_meals(date_from: str, date_to: str) -> list[dict]:
    """All members' meals in a date range, oldest first, for CSV export."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT eaten_at, member, meal_type, description, kcal_total,
                      protein_g, carbs_g, fat_g, logged_by
               FROM meals WHERE DATE(eaten_at) >= ? AND DATE(eaten_at) <= ?
               ORDER BY eaten_at""",
            (date_from, date_to),
        )
        rows = await cur.fetchall()
    columns = ("eaten_at", "member", "meal_type", "description", "kcal_total",
               "protein_g", "carbs_g", "fat_g", "logged_by")
    return [dict(zip(columns, r)) for r in rows]


async def list_members_with_meals(day: str) -> list[str]:
    """Members who logged at least one meal on a given day."""
    async with connect() as db:
        cur = await db.execute(
            "SELECT DISTINCT member FROM meals WHERE DATE(eaten_at) = ? ORDER BY member",
            (day,),
        )
        rows = await cur.fetchall()
    return [r[0] for r in rows]
