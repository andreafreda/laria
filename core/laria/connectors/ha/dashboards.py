"""LARIA-native MQTT dashboard publisher: clean, English, product-owned entities.

This is the canonical publisher. It exposes LARIA's data as Home Assistant sensors
under the ``laria_`` namespace with an English, self-describing entity model and
per-domain LARIA devices, so the product is fully decoupled from HARIA. The
transitional HARIA-compat publisher (``compat.py``) mirrors the same data under
HARIA's old ids and is removed once the dashboards point here.

Only the *structural* terms are English (utility/finance/diet, balance, budget,
goal, kcal_today, ...). Instance labels a household types in (account, category,
goal, member names) stay as the user's own data.
"""
from __future__ import annotations

from datetime import date

from ...services.macros import compute_macro_targets
from ...storage import finance, food, utilities
from . import _mqtt_model as m
from ._mqtt_model import Sensor

_DEVICE_FINANCE = {"identifiers": ["laria_finance"], "name": "LARIA Finance",
                   "manufacturer": "LARIA", "model": "finance"}
_DEVICE_UTILITIES = {"identifiers": ["laria_utilities"], "name": "LARIA Utilities",
                     "manufacturer": "LARIA", "model": "utilities"}
_DEVICE_DIET = {"identifiers": ["laria_diet"], "name": "LARIA Diet",
                "manufacturer": "LARIA", "model": "diet"}

_STATE_FINANCE = "laria/finance"
_STATE_UTILITY = "laria/utility"
_STATE_DIET = "laria/diet"

# Structural translation for the utility series (instance data is Italian).
# HA composes an MQTT entity's id as slug(device_name)_slug(name) when a device
# and name are given, so these translated words drive the final entity_id. The
# migrated data stores the cost metric as Italian "costo"; map it (and the older
# "eur" token) to "cost".
_UTILITY_EN = {"corrente": "electricity", "acqua": "water", "gas": "gas"}
_METRIC_EN = {"costo": "cost", "eur": "cost", "kwh": "kwh", "m3": "m3"}


def _utility_en(name: str) -> str:
    return _UTILITY_EN.get(name, m.slug(name))


def _metric_en(name: str) -> str:
    return _METRIC_EN.get(name, m.slug(name))


# ---------------------------------------------------------------- utilities

async def collect_utilities(today: date | None = None) -> list[Sensor]:
    """One sensor per (utility, metric, year), state = the 12 month CSV.

    Years are padded to a rolling three year window so a year card never shows
    "unavailable" for a year without data yet (the CSV is zeros).
    """
    today = today or date.today()
    sensors: list[Sensor] = []
    for utility, metric in await utilities.list_bill_series():
        util_en, metric_en = _utility_en(utility), _metric_en(metric)
        years = set(await utilities.get_bill_years(utility, metric))
        years |= {today.year, today.year - 1, today.year - 2}
        for year in sorted(years):
            csv = await utilities.get_bill_csv(utility, metric, year)
            uid = f"laria_utility_{util_en}_{metric_en}_{year}"
            sensors.append(Sensor(
                uid=uid, object_id=uid, name=f"{util_en.capitalize()} {metric_en} {year}",
                device=_DEVICE_UTILITIES,
                state_topic=f"{_STATE_UTILITY}/{util_en}/{metric_en}/{year}", value=csv,
            ))
    return sensors


# ---------------------------------------------------------------- finance

async def collect_finance(today: date | None = None) -> list[Sensor]:
    """Balances, monthly spending, budgets, goals, and the history matrices."""
    today = today or date.today()
    sensors: list[Sensor] = []
    sensors += await _balance_sensors()
    sensors += await _spending_sensors(today)
    sensors += await _budget_sensors(today)
    sensors += await _goal_sensors()
    sensors += await _history_sensors()
    sensors.append(await _month_transactions_sensor(today))
    return sensors


async def _month_transactions_sensor(today: date) -> Sensor:
    _, _, year, month = m.month_bounds(today)
    rows = await finance.month_transactions(year, month)
    return _finance(
        "laria_finance_transactions_month", "Transactions month",
        f"{_STATE_FINANCE}/transactions_month/state", len(rows),
        icon="mdi:format-list-bulleted-square",
        attr_topic=f"{_STATE_FINANCE}/transactions_month/attr", attr={"rows": rows})


def _finance(uid: str, name: str, topic: str, value: object, **extra) -> Sensor:
    return Sensor(uid=uid, object_id=uid, name=name, device=_DEVICE_FINANCE,
                  state_topic=topic, value=value, **extra)


async def _balance_sensors() -> list[Sensor]:
    balances = await finance.get_balances()
    sensors: list[Sensor] = []
    total = 0.0
    per_owner: dict[str, float] = {}
    for row in balances:
        s = m.slug(row["account"])
        sensors.append(_finance(
            f"laria_finance_balance_{s}", f"Balance {row['account']}",
            f"{_STATE_FINANCE}/balance/{s}", row["balance"],
            unit="€", icon="mdi:wallet", state_class="measurement"))
        total += row["balance"]
        owner = row.get("owner") or "family"
        per_owner[owner] = round(per_owner.get(owner, 0.0) + row["balance"], 2)
    sensors.append(_finance(
        "laria_finance_total_balance", "Total balance",
        f"{_STATE_FINANCE}/total_balance", round(total, 2),
        unit="€", icon="mdi:cash-multiple", state_class="measurement"))
    for owner, value in per_owner.items():
        s = m.slug(owner)
        sensors.append(_finance(
            f"laria_finance_balance_owner_{s}", f"Balance owner {owner}",
            f"{_STATE_FINANCE}/balance_owner/{s}", value,
            unit="€", icon="mdi:account-cash", state_class="measurement"))
    return sensors


async def _spending_sensors(today: date) -> list[Sensor]:
    first, last, _, _ = m.month_bounds(today)
    rep = await finance.expense_summary(date_from=first, date_to=last)
    # expenses are negative; show the amount spent. ``or 0.0`` collapses -0.0.
    spent = round(-rep["expenses"], 2) or 0.0
    sensors = [_finance(
        "laria_finance_spending_month", "Spending this month",
        f"{_STATE_FINANCE}/spending_month/state", spent, unit="€",
        icon="mdi:cart-arrow-down", attr_topic=f"{_STATE_FINANCE}/spending_month/attr",
        attr={"income": rep["income"], "expenses": rep["expenses"], "net": rep["net"],
              "by_category": {c["category"]: c["total"] for c in rep["by_category"]}})]
    prev_first, prev_last = m.prev_month_bounds(today)
    prev = await finance.expense_summary(date_from=prev_first, date_to=prev_last)
    spent_prev = round(-prev["expenses"], 2) or 0.0
    sensors.append(_finance(
        "laria_finance_spending_prev_month", "Spending previous month",
        f"{_STATE_FINANCE}/spending_prev_month", spent_prev, unit="€",
        icon="mdi:cart-outline"))
    sensors.append(_finance(
        "laria_finance_spending_delta", "Spending vs previous month",
        f"{_STATE_FINANCE}/spending_delta", round(spent - spent_prev, 2) or 0.0,
        unit="€", icon="mdi:swap-vertical"))
    return sensors


async def _budget_sensors(today: date) -> list[Sensor]:
    _, _, year, month = m.month_bounds(today)
    sensors: list[Sensor] = []
    for b in await finance.get_budget_status(year, month):
        s = m.slug(b["category"])
        base = f"{_STATE_FINANCE}/budget/{s}"
        sensors.append(_finance(
            f"laria_finance_budget_{s}", f"Budget {b['category']}",
            f"{base}/state", b["perc"], unit="%", icon="mdi:gauge",
            attr_topic=f"{base}/attr",
            attr={"budget": b["budget"], "spent": b["spent"],
                  "remaining": b["remaining"], "over": b["over"]}))
    return sensors


async def _goal_sensors() -> list[Sensor]:
    sensors: list[Sensor] = []
    for g in await finance.get_goals():
        s = m.slug(g["name"])
        base = f"{_STATE_FINANCE}/goal/{s}"
        sensors.append(_finance(
            f"laria_finance_goal_{s}", f"Goal {g['name']}",
            f"{base}/state", g["perc"], unit="%", icon="mdi:piggy-bank",
            attr_topic=f"{base}/attr",
            attr={"target": g["target"], "saved": g["saved"], "remaining": g["remaining"],
                  "deadline": g["target_date"] or "",
                  "months_left": g["months_left"] if g["months_left"] is not None else "",
                  "monthly_quota": g["monthly_quota"] if g["monthly_quota"] is not None else "",
                  "reached": g["reached"]}))
    return sensors


async def _history_sensors() -> list[Sensor]:
    matrix = await finance.monthly_category_matrix()
    months, categories, totals = matrix["months"], matrix["categories"], matrix["totals"]
    averages = ({cat: round(sum(vals) / len(months), 2) for cat, vals in categories.items()}
                if months else {})
    history = _finance(
        "laria_finance_spending_history", "Monthly spending history",
        f"{_STATE_FINANCE}/spending_history/state", len(months), icon="mdi:table-large",
        attr_topic=f"{_STATE_FINANCE}/spending_history/attr",
        attr={"months": months, "categories": categories, "totals": totals, "averages": averages})
    transactions = await finance.recent_transactions()
    moves = [{"date": t["date"], "amount": t["amount"], "category": t["category"],
              "description": (t["description"] or "").strip()[:32]} for t in transactions]
    movements = _finance(
        "laria_finance_recent_transactions", "Recent transactions",
        f"{_STATE_FINANCE}/recent_transactions/state", len(moves),
        icon="mdi:format-list-bulleted",
        attr_topic=f"{_STATE_FINANCE}/recent_transactions/attr",
        attr={"transactions": moves})
    return [history, movements]


# ---------------------------------------------------------------- diet

async def collect_diet(today: date | None = None) -> list[Sensor]:
    """Per member nutrition and weight, plus the shared plan, shopping, and pantry."""
    today = today or date.today()
    sensors: list[Sensor] = []
    for profile in await food.list_profiles():
        sensors += await _member_sensors(profile["member"], today)
    sensors += await _plan_sensors(today)
    sensors += await _shopping_pantry_sensors()
    return sensors


async def _member_sensors(member: str, today: date) -> list[Sensor]:
    s = m.slug(member)
    base = f"{_STATE_DIET}/{s}"
    cap = member.capitalize()
    today_iso = today.isoformat()

    totals = await food.get_day_totals(member, today_iso)
    hydration = await food.get_hydration_day(member, today_iso)
    profile = await food.get_profile(member)
    kcal_target = profile.get("kcal_target") if profile else None
    macros = compute_macro_targets(kcal_target, profile.get("weight_kg") if profile else None)
    stats = await food.get_weight_stats(member, 30)

    def sensor(suffix, name, value, unit="", icon=None, **extra):
        uid = f"laria_diet_{s}_{suffix}"
        return Sensor(uid=uid, object_id=uid, name=f"{cap} {name}", device=_DEVICE_DIET,
                      state_topic=f"{base}/{suffix}", value=value, unit=unit, icon=icon, **extra)

    blank = ""
    sensors = [
        sensor("kcal_today", "kcal today", round(totals["kcal"]), "kcal", "mdi:fire"),
        sensor("kcal_target", "kcal target", kcal_target if kcal_target is not None else blank,
               "kcal", "mdi:target"),
        sensor("protein_today", "protein today", round(totals["protein_g"]), "g",
               "mdi:food-drumstick"),
        sensor("protein_target", "protein target",
               macros["protein_target_g"] if macros else blank, "g", "mdi:food-drumstick-outline"),
        sensor("carbs_today", "carbs today", round(totals["carbs_g"]), "g", "mdi:bread-slice"),
        sensor("carbs_target", "carbs target",
               macros["carbs_target_g"] if macros else blank, "g", "mdi:bread-slice-outline"),
        sensor("fat_today", "fat today", round(totals["fat_g"]), "g", "mdi:oil"),
        sensor("fat_target", "fat target", macros["fat_target_g"] if macros else blank, "g", "mdi:oil"),
        sensor("water_today", "water today", round(hydration["ml_total"]), "mL", "mdi:cup-water"),
    ]
    if stats:
        weight = stats["latest"]
        bmi = stats["latest_bmi"] if stats["latest_bmi"] is not None else (
            profile.get("bmi") if profile else None)
        sensors.append(sensor("weight_delta_30d", "weight delta 30d", stats["delta"], "kg",
                              "mdi:scale-balance"))
        sensors.append(sensor("weight_min_30d", "weight min 30d", stats["min"], "kg",
                              "mdi:arrow-down-bold"))
        sensors.append(sensor("weight_max_30d", "weight max 30d", stats["max"], "kg",
                              "mdi:arrow-up-bold"))
    else:
        weight = profile.get("weight_kg") if profile else None
        bmi = profile.get("bmi") if profile else None
        sensors.append(sensor("weight_delta_30d", "weight delta 30d", blank, "kg", "mdi:scale-balance"))
        sensors.append(sensor("weight_min_30d", "weight min 30d", blank, "kg", "mdi:arrow-down-bold"))
        sensors.append(sensor("weight_max_30d", "weight max 30d", blank, "kg", "mdi:arrow-up-bold"))
    sensors.append(sensor("weight", "weight", weight if weight is not None else blank, "kg",
                          "mdi:scale-bathroom", state_class="measurement", device_class="weight"))
    sensors.append(sensor("bmi", "BMI", bmi if bmi is not None else blank, icon="mdi:human",
                          state_class="measurement"))
    sensors.append(await _diary_sensor(member, s, base, cap, today))
    return sensors


async def _diary_sensor(member: str, s: str, base: str, cap: str, today: date) -> Sensor:
    days = m.week_days(today)
    meals = await food.get_meals(member, days[0].isoformat(), days[-1].isoformat())
    by_day: dict[str, list[dict]] = {}
    for meal in meals:
        by_day.setdefault((meal.get("eaten_at") or "")[:10], []).append(meal)
    attr: dict[str, str] = {}
    for day in days:
        iso = day.isoformat()
        ordered = sorted(by_day.get(iso, []), key=lambda x: m.MEAL_ORDER.get(x["meal_type"], 9))
        attr[iso] = "; ".join(
            f"{x['meal_type']}: {x['description']}"
            + (f" ({round(x['kcal_total'])} kcal)" if x.get("kcal_total") else "")
            for x in ordered)
    return Sensor(
        uid=f"laria_diet_{s}_diary_week", object_id=f"laria_diet_{s}_diary_week",
        name=f"{cap} diary week", device=_DEVICE_DIET,
        state_topic=f"{base}/diary_week/state",
        value=f"{len(meals)} meals" if meals else "no meals",
        icon="mdi:book-open-variant", attr_topic=f"{base}/diary_week/attr", attr=attr)


def _diet(uid: str, name: str, topic: str, value: object, **extra) -> Sensor:
    return Sensor(uid=uid, object_id=uid, name=name, device=_DEVICE_DIET,
                  state_topic=topic, value=value, **extra)


async def _plan_sensors(today: date) -> list[Sensor]:
    today_iso = today.isoformat()
    day_plan = await food.get_meal_plan(today_iso, today_iso)
    day_plan.sort(key=lambda x: (m.MEAL_ORDER.get(x["meal_type"], 9), x.get("member") or ""))
    day_attr: dict[str, str] = {}
    for meal_type in ("colazione", "pranzo", "snack", "cena"):
        group = [x for x in day_plan if x["meal_type"] == meal_type]
        if group:
            day_attr[meal_type] = "; ".join(m.fmt_plan_item(x) for x in group)

    week = m.week_days(today)
    week_plan = await food.get_meal_plan(week[0].isoformat(), week[-1].isoformat())
    month = m.month_days(today)
    month_plan = await food.get_meal_plan(month[0].isoformat(), month[-1].isoformat())

    return [
        _diet("laria_diet_plan_today", "Plan today", f"{_STATE_DIET}/plan_today/state",
              f"{len(day_plan)} meals" if day_plan else "no plan",
              icon="mdi:silverware-fork-knife", attr_topic=f"{_STATE_DIET}/plan_today/attr",
              attr=day_attr),
        _diet("laria_diet_plan_week", "Plan week", f"{_STATE_DIET}/plan_week/state",
              f"{len(week_plan)} meals", icon="mdi:calendar-week",
              attr_topic=f"{_STATE_DIET}/plan_week/attr", attr=m.plan_by_day(week_plan, week)),
        _diet("laria_diet_plan_month", "Plan month", f"{_STATE_DIET}/plan_month/state",
              f"{len(month_plan)} meals", icon="mdi:calendar-month",
              attr_topic=f"{_STATE_DIET}/plan_month/attr", attr=m.plan_by_day(month_plan, month)),
    ]


async def _shopping_pantry_sensors() -> list[Sensor]:
    items = await food.get_shopping_list(include_checked=False)
    cost = await food.get_shopping_cost(include_checked=True)
    pantry = await food.get_pantry()
    expiring = await food.get_pantry_expiring(3)
    return [
        _diet("laria_diet_shopping_list", "Shopping list", f"{_STATE_DIET}/shopping_list/state",
              len(items), unit="items", icon="mdi:cart",
              attr_topic=f"{_STATE_DIET}/shopping_list/attr",
              attr={"items": [m.fmt_shopping(it) for it in items]}),
        _diet("laria_diet_shopping_cost", "Shopping cost", f"{_STATE_DIET}/shopping_cost/state",
              cost["total"], unit="€", icon="mdi:currency-eur",
              attr_topic=f"{_STATE_DIET}/shopping_cost/attr",
              attr={"priced": cost["priced"], "missing": cost["missing"], "total": cost["count"]}),
        _diet("laria_diet_pantry", "Pantry", f"{_STATE_DIET}/pantry/state", len(pantry),
              unit="items", icon="mdi:fridge", attr_topic=f"{_STATE_DIET}/pantry/attr",
              attr={"items": [m.fmt_pantry(it) for it in pantry]}),
        _diet("laria_diet_pantry_expiring", "Pantry expiring",
              f"{_STATE_DIET}/pantry_expiring/state", len(expiring), unit="items",
              icon="mdi:clock-alert", attr_topic=f"{_STATE_DIET}/pantry_expiring/attr",
              attr={"items": [m.fmt_pantry(it) for it in expiring]}),
    ]


# ---------------------------------------------------------------- publish

_COLLECTORS = {"utilities": collect_utilities, "finance": collect_finance, "diet": collect_diet}


async def publish_native(mirror) -> None:
    """Publish every LARIA-native dashboard kind, retiring entities that vanished."""
    await m.publish_kinds(mirror, _COLLECTORS)
