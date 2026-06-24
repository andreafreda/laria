"""Food storage: diet profiles, weight log, meals, weekly plan, hydration,
shopping list, pantry, nutrition cache. Ported from HARIA ``memory/food.py``.

``member`` is a free-text family-member identifier (no hardcoded members).
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from .db import connect

_PROFILE_FIELDS = (
    "member", "sex", "age", "height_cm", "weight_kg", "goal",
    "activity_level", "kcal_target", "bmi", "allergies", "preferences", "restrictions",
)


def _profile_row(r) -> dict:
    return dict(zip(_PROFILE_FIELDS, r))


# --------------------------------------------------------------------------- #
# Diet profiles
# --------------------------------------------------------------------------- #

async def get_profile(member: str) -> dict | None:
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
    async with connect() as db:
        cur = await db.execute("DELETE FROM diet_profiles WHERE member = ?", (member,))
        await db.commit()
        return cur.rowcount > 0


async def upsert_profile(member: str, fields: dict) -> None:
    """Insert or update a profile. Only fields present in ``fields`` are touched."""
    cols = [k for k in fields if k in _PROFILE_FIELDS and k != "member"]
    async with connect() as db:
        exists = await (await db.execute(
            "SELECT 1 FROM diet_profiles WHERE member = ?", (member,)
        )).fetchone()
        if exists:
            if cols:
                sets = ", ".join(f"{c} = ?" for c in cols) + ", updated_at = CURRENT_TIMESTAMP"
                await db.execute(
                    f"UPDATE diet_profiles SET {sets} WHERE member = ?",
                    [fields[c] for c in cols] + [member],
                )
        else:
            allcols = ["member"] + cols
            placeholders = ", ".join("?" for _ in allcols)
            await db.execute(
                f"INSERT INTO diet_profiles ({', '.join(allcols)}) VALUES ({placeholders})",
                [member] + [fields[c] for c in cols],
            )
        await db.commit()


async def list_profiles() -> list[dict]:
    async with connect() as db:
        cur = await db.execute(
            """SELECT member, sex, age, height_cm, weight_kg, goal, activity_level,
                      kcal_target, bmi FROM diet_profiles ORDER BY member"""
        )
        rows = await cur.fetchall()
    cols = ("member", "sex", "age", "height_cm", "weight_kg", "goal",
            "activity_level", "kcal_target", "bmi")
    return [dict(zip(cols, r)) for r in rows]


# --------------------------------------------------------------------------- #
# Weight log
# --------------------------------------------------------------------------- #

async def add_weight(member: str, weight_kg: float, bmi: float | None) -> dict:
    async with connect() as db:
        cur = await db.execute(
            "INSERT INTO weight_log (member, weight_kg, bmi) VALUES (?, ?, ?)",
            (member, weight_kg, bmi),
        )
        await db.commit()
        wid = cur.lastrowid
    return {"id": wid, "member": member, "weight_kg": weight_kg, "bmi": bmi}


async def get_weight_history(member: str, limit: int = 20) -> list[dict]:
    async with connect() as db:
        cur = await db.execute(
            """SELECT id, weight_kg, bmi, logged_at FROM weight_log
               WHERE member = ? ORDER BY logged_at DESC LIMIT ?""",
            (member, limit),
        )
        rows = await cur.fetchall()
    return [{"id": i, "weight_kg": w, "bmi": b, "logged_at": t} for i, w, b, t in rows]


async def update_weight(weight_id: int, weight_kg: float | None = None,
                        bmi: float | None = None) -> bool:
    sets: list[str] = []
    params: list = []
    if weight_kg is not None:
        sets.append("weight_kg = ?"); params.append(weight_kg)
    if bmi is not None:
        sets.append("bmi = ?"); params.append(bmi)
    if not sets:
        return False
    params.append(int(weight_id))
    async with connect() as db:
        cur = await db.execute(
            f"UPDATE weight_log SET {', '.join(sets)} WHERE id = ?", params
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_weight(weight_id: int) -> bool:
    async with connect() as db:
        cur = await db.execute("DELETE FROM weight_log WHERE id = ?", (int(weight_id),))
        await db.commit()
        return cur.rowcount > 0


async def get_weight_stats(member: str, days: int = 30) -> dict | None:
    """Weight stats over a ``days`` window: latest, min, max, delta, count."""
    since = (date.today() - timedelta(days=days)).isoformat()
    async with connect() as db:
        cur = await db.execute(
            """SELECT weight_kg, bmi, logged_at FROM weight_log
               WHERE member = ? AND logged_at >= ?
               ORDER BY logged_at ASC""",
            (member, since),
        )
        rows = await cur.fetchall()
    if not rows:
        async with connect() as db:
            cur = await db.execute(
                """SELECT weight_kg, bmi, logged_at FROM weight_log
                   WHERE member = ? ORDER BY logged_at DESC LIMIT 1""",
                (member,),
            )
            last = await cur.fetchone()
        if not last:
            return None
        w, b, t = last
        return {"latest": w, "latest_bmi": b, "latest_at": t,
                "min": w, "max": w, "delta": 0.0, "count": 1, "days": days}
    weights = [r[0] for r in rows]
    first_w = weights[0]
    last_w, last_b, last_t = rows[-1]
    return {
        "latest": last_w, "latest_bmi": last_b, "latest_at": last_t,
        "min": min(weights), "max": max(weights),
        "delta": round(last_w - first_w, 1), "count": len(rows), "days": days,
    }


# --------------------------------------------------------------------------- #
# Meals
# --------------------------------------------------------------------------- #

async def add_meal(member: str, meal_type: str, description: str, totals: dict,
                   items: list[dict], eaten_at: str | None, logged_by: str | None) -> dict:
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
        for it in items or []:
            await db.execute(
                """INSERT INTO meal_items
                   (meal_id, name, grams, kcal, protein_g, carbs_g, fat_g,
                    fiber_g, sugar_g, sat_fat_g, sodium_mg,
                    vit_c_mg, vit_d_ug, iron_mg, calcium_mg, potassium_mg, magnesium_mg)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (meal_id, it.get("name"), it.get("grams"), it.get("kcal"),
                 it.get("protein_g"), it.get("carbs_g"), it.get("fat_g"),
                 it.get("fiber_g"), it.get("sugar_g"),
                 it.get("sat_fat_g"), it.get("sodium_mg"),
                 it.get("vit_c_mg"), it.get("vit_d_ug"), it.get("iron_mg"),
                 it.get("calcium_mg"), it.get("potassium_mg"), it.get("magnesium_mg")),
            )
        await db.commit()
    return {"id": meal_id, "member": member, "meal_type": meal_type}


async def update_meal(meal_id: int, meal_type: str | None = None, description: str | None = None,
                      totals: dict | None = None, eaten_at: str | None = None) -> bool:
    """Edit a logged meal. Only supplied fields are updated."""
    sets: list[str] = []
    params: list = []
    if meal_type is not None:
        sets.append("meal_type = ?"); params.append(meal_type)
    if description is not None:
        sets.append("description = ?"); params.append(description)
    if eaten_at is not None:
        sets.append("eaten_at = ?"); params.append(eaten_at)
    if totals:
        for col in ("kcal_total", "protein_g", "carbs_g", "fat_g"):
            if totals.get(col) is not None:
                sets.append(f"{col} = ?"); params.append(totals[col])
    if not sets:
        return False
    params.append(int(meal_id))
    async with connect() as db:
        cur = await db.execute(f"UPDATE meals SET {', '.join(sets)} WHERE id = ?", params)
        await db.commit()
        return cur.rowcount > 0


async def delete_meal(meal_id: int) -> bool:
    """Delete a logged meal (and its meal_items)."""
    async with connect() as db:
        await db.execute("DELETE FROM meal_items WHERE meal_id = ?", (int(meal_id),))
        cur = await db.execute("DELETE FROM meals WHERE id = ?", (int(meal_id),))
        await db.commit()
        return cur.rowcount > 0


async def get_meals(member: str, date_from: str | None = None,
                    date_to: str | None = None) -> list[dict]:
    q = ("SELECT id, meal_type, description, kcal_total, protein_g, carbs_g, fat_g, eaten_at "
         "FROM meals WHERE member = ?")
    params: list = [member]
    if date_from:
        q += " AND DATE(eaten_at) >= DATE(?)"; params.append(date_from)
    if date_to:
        q += " AND DATE(eaten_at) <= DATE(?)"; params.append(date_to)
    q += " ORDER BY eaten_at DESC LIMIT 50"
    async with connect() as db:
        cur = await db.execute(q, params)
        rows = await cur.fetchall()
    return [
        {"id": r[0], "meal_type": r[1], "description": r[2], "kcal_total": r[3],
         "protein_g": r[4], "carbs_g": r[5], "fat_g": r[6], "eaten_at": r[7]}
        for r in rows
    ]


async def get_logged_days(days_back: int = 30) -> list[dict]:
    """Days with logged meals in the last N days: [{day, members, meals, kcal}]."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT DATE(eaten_at) AS d,
                      COUNT(DISTINCT member) AS members,
                      COUNT(*) AS meals,
                      COALESCE(SUM(kcal_total), 0) AS kcal
               FROM meals
               WHERE DATE(eaten_at) >= DATE('now', ?)
               GROUP BY d ORDER BY d DESC""",
            (f"-{int(days_back)} days",),
        )
        rows = await cur.fetchall()
    return [{"day": r[0], "members": r[1], "meals": r[2], "kcal": round(r[3], 1)} for r in rows]


async def get_day_totals(member: str, day: str) -> dict:
    """Sum kcal/macros/micros of a member's meals on a day (YYYY-MM-DD)."""
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
    """All meals of all members in a range (for CSV export)."""
    async with connect() as db:
        cur = await db.execute(
            """SELECT eaten_at, member, meal_type, description, kcal_total,
                      protein_g, carbs_g, fat_g, logged_by
               FROM meals WHERE DATE(eaten_at) >= ? AND DATE(eaten_at) <= ?
               ORDER BY eaten_at""",
            (date_from, date_to),
        )
        rows = await cur.fetchall()
    cols = ("eaten_at", "member", "meal_type", "description", "kcal_total",
            "protein_g", "carbs_g", "fat_g", "logged_by")
    return [dict(zip(cols, r)) for r in rows]


async def list_members_with_meals(day: str) -> list[str]:
    async with connect() as db:
        cur = await db.execute(
            "SELECT DISTINCT member FROM meals WHERE DATE(eaten_at) = ? ORDER BY member",
            (day,),
        )
        rows = await cur.fetchall()
    return [r[0] for r in rows]


# --------------------------------------------------------------------------- #
# Weekly meal plan
# --------------------------------------------------------------------------- #

async def set_plan_meal(date: str, meal_type: str, items: str,
                        recipe: str | None = None, servings: int | None = None,
                        kcal: float | None = None, member: str | None = None) -> None:
    """Insert or replace a planned meal (key date+meal_type+member).
    Empty member = shared plan; a member value = personal override."""
    member = (member or "").strip().lower()
    async with connect() as db:
        await db.execute(
            """INSERT INTO meal_plan (date, meal_type, member, items, recipe, servings, kcal, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(date, meal_type, member) DO UPDATE SET
                 items=excluded.items, recipe=excluded.recipe,
                 servings=excluded.servings, kcal=excluded.kcal,
                 updated_at=CURRENT_TIMESTAMP""",
            (date, meal_type, member, items, recipe, servings, kcal),
        )
        await db.commit()


async def delete_plan_meal(date: str, meal_type: str, member: str | None = None) -> int:
    member = (member or "").strip().lower()
    async with connect() as db:
        cur = await db.execute(
            "DELETE FROM meal_plan WHERE date = ? AND meal_type = ? AND member = ?",
            (date, meal_type, member),
        )
        await db.commit()
        return cur.rowcount


async def get_meal_plan(date_from: str, date_to: str) -> list[dict]:
    async with connect() as db:
        cur = await db.execute(
            """SELECT date, meal_type, member, items, recipe, servings, kcal FROM meal_plan
               WHERE date >= ? AND date <= ? ORDER BY date, meal_type, member""",
            (date_from, date_to),
        )
        rows = await cur.fetchall()
    return [
        {"date": r[0], "meal_type": r[1], "member": r[2], "items": r[3],
         "recipe": r[4], "servings": r[5], "kcal": r[6]}
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# Hydration
# --------------------------------------------------------------------------- #

async def add_hydration(member: str, ml: float) -> dict:
    async with connect() as db:
        cur = await db.execute(
            "INSERT INTO hydration_log (member, ml) VALUES (?, ?)", (member, ml)
        )
        await db.commit()
        hid = cur.lastrowid
    return {"id": hid, "member": member, "ml": ml}


async def delete_last_hydration(member: str) -> bool:
    """Undo the member's last hydration log for today."""
    async with connect() as db:
        row = await (await db.execute(
            """SELECT id FROM hydration_log
               WHERE member = ? AND DATE(logged_at) = DATE('now', 'localtime')
               ORDER BY logged_at DESC LIMIT 1""",
            (member,),
        )).fetchone()
        if not row:
            return False
        cur = await db.execute("DELETE FROM hydration_log WHERE id = ?", (row[0],))
        await db.commit()
        return cur.rowcount > 0


async def get_hydration_day(member: str, day: str) -> dict:
    async with connect() as db:
        cur = await db.execute(
            """SELECT COALESCE(SUM(ml),0), COUNT(*) FROM hydration_log
               WHERE member = ? AND DATE(logged_at) = ?""",
            (member, day),
        )
        r = await cur.fetchone()
    return {"ml_total": round(r[0], 1), "count": r[1]}


# --------------------------------------------------------------------------- #
# Shopping list
# --------------------------------------------------------------------------- #

async def add_shopping_items(items: list[dict]) -> int:
    async with connect() as db:
        for it in items or []:
            await db.execute(
                "INSERT INTO shopping_items (name, qty, category, price) VALUES (?, ?, ?, ?)",
                (it.get("name"), it.get("qty"), it.get("category"), it.get("price")),
            )
        await db.commit()
    return len(items or [])


async def get_shopping_list(include_checked: bool = False) -> list[dict]:
    q = "SELECT id, name, qty, category, checked, price FROM shopping_items"
    if not include_checked:
        q += " WHERE checked = 0"
    q += " ORDER BY category, name"
    async with connect() as db:
        cur = await db.execute(q)
        rows = await cur.fetchall()
    return [{"id": r[0], "name": r[1], "qty": r[2], "category": r[3],
             "checked": bool(r[4]), "price": r[5]} for r in rows]


async def set_shopping_price(name: str, price: float) -> bool:
    """Set the price of a shopping item by name (partial match)."""
    if not (name or "").strip():
        return False
    async with connect() as db:
        cur = await db.execute(
            "UPDATE shopping_items SET price = ? WHERE LOWER(name) LIKE LOWER(?)",
            (price, f"%{name}%"),
        )
        await db.commit()
        return cur.rowcount > 0


async def remove_shopping_item(name: str) -> int:
    """Remove shopping items by name (partial match)."""
    if not (name or "").strip():
        return 0
    async with connect() as db:
        cur = await db.execute(
            "DELETE FROM shopping_items WHERE LOWER(name) LIKE LOWER(?)", (f"%{name}%",)
        )
        await db.commit()
        return cur.rowcount


async def get_shopping_cost(include_checked: bool = True) -> dict:
    """Total shopping-list cost. Returns {total, priced, missing, count}."""
    q = "SELECT price FROM shopping_items"
    if not include_checked:
        q += " WHERE checked = 0"
    async with connect() as db:
        cur = await db.execute(q)
        rows = await cur.fetchall()
    total = round(sum(r[0] for r in rows if r[0] is not None), 2)
    priced = sum(1 for r in rows if r[0] is not None)
    return {"total": total, "priced": priced, "missing": len(rows) - priced, "count": len(rows)}


async def check_shopping_item(name: str) -> bool:
    if not (name or "").strip():
        return False
    async with connect() as db:
        cur = await db.execute(
            "UPDATE shopping_items SET checked = 1 WHERE checked = 0 AND LOWER(name) LIKE LOWER(?)",
            (f"%{name}%",),
        )
        await db.commit()
        return cur.rowcount > 0


async def toggle_shopping_item(item_id: int) -> bool:
    async with connect() as db:
        cur = await db.execute(
            "UPDATE shopping_items SET checked = 1 - checked WHERE id = ?", (int(item_id),)
        )
        await db.commit()
        return cur.rowcount > 0


async def clear_shopping_list(only_checked: bool = False) -> int:
    async with connect() as db:
        if only_checked:
            cur = await db.execute("DELETE FROM shopping_items WHERE checked = 1")
        else:
            cur = await db.execute("DELETE FROM shopping_items")
        await db.commit()
        return cur.rowcount


# --------------------------------------------------------------------------- #
# Pantry
# --------------------------------------------------------------------------- #

async def add_pantry_items(items: list[dict]) -> int:
    """Add pantry items. Each item: name, qty?, category?, expires_on?"""
    n = 0
    async with connect() as db:
        for it in items:
            name = (it.get("name") or "").strip()
            if not name:
                continue
            await db.execute(
                """INSERT INTO pantry_items (name, qty, category, expires_on, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (name, it.get("qty"), it.get("category"), it.get("expires_on")),
            )
            n += 1
        await db.commit()
    return n


async def get_pantry(category: str | None = None) -> list[dict]:
    q = "SELECT id, name, qty, category, expires_on FROM pantry_items"
    params: list = []
    if category:
        q += " WHERE category = ?"; params.append(category)
    q += " ORDER BY (expires_on IS NULL), expires_on, name"
    async with connect() as db:
        cur = await db.execute(q, params)
        rows = await cur.fetchall()
    return [{"id": r[0], "name": r[1], "qty": r[2], "category": r[3], "expires_on": r[4]}
            for r in rows]


async def get_pantry_expiring(within_days: int = 3) -> list[dict]:
    """Items expiring within N days (or already expired)."""
    limit = (date.today() + timedelta(days=within_days)).isoformat()
    async with connect() as db:
        cur = await db.execute(
            """SELECT id, name, qty, category, expires_on FROM pantry_items
               WHERE expires_on IS NOT NULL AND expires_on <= ?
               ORDER BY expires_on""",
            (limit,),
        )
        rows = await cur.fetchall()
    return [{"id": r[0], "name": r[1], "qty": r[2], "category": r[3], "expires_on": r[4]}
            for r in rows]


async def consume_pantry_item(name: str) -> int:
    """Remove a pantry item by exact (case-insensitive) name."""
    async with connect() as db:
        cur = await db.execute(
            "DELETE FROM pantry_items WHERE LOWER(name) = ?", ((name or "").strip().lower(),)
        )
        await db.commit()
        return cur.rowcount


async def update_pantry_item(name: str, qty: str | None = None,
                             category: str | None = None,
                             expires_on: str | None = None) -> int:
    """Edit pantry items by name (partial match). Only supplied fields."""
    sets: list[str] = []
    params: list = []
    if qty is not None:
        sets.append("qty = ?"); params.append(qty)
    if category is not None:
        sets.append("category = ?"); params.append(category)
    if expires_on is not None:
        sets.append("expires_on = ?"); params.append(expires_on or None)
    if not sets:
        return 0
    if not (name or "").strip():
        return 0
    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(f"%{name}%")
    async with connect() as db:
        cur = await db.execute(
            f"UPDATE pantry_items SET {', '.join(sets)} WHERE LOWER(name) LIKE LOWER(?)",
            params,
        )
        await db.commit()
        return cur.rowcount


async def clear_pantry() -> int:
    async with connect() as db:
        cur = await db.execute("DELETE FROM pantry_items")
        await db.commit()
        return cur.rowcount


# --------------------------------------------------------------------------- #
# Nutrition value cache
# --------------------------------------------------------------------------- #

FOOD_CACHE_TTL_DAYS = 90


async def get_food_cache(key: str) -> dict | None:
    async with connect() as db:
        cur = await db.execute(
            "SELECT data, source FROM food_cache WHERE key = ? "
            "AND updated_at > datetime('now', ?)",
            (key.lower(), f"-{FOOD_CACHE_TTL_DAYS} days"),
        )
        row = await cur.fetchone()
    if not row:
        return None
    d = json.loads(row[0])
    d["_source"] = row[1]
    return d


async def set_food_cache(key: str, data: dict, source: str) -> None:
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
            (f"-{FOOD_CACHE_TTL_DAYS} days",),
        )
        await db.commit()
