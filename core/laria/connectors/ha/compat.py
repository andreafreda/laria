"""Publish LARIA data as the exact MQTT entities HARIA used to publish.

HARIA fed a set of Home Assistant Lovelace dashboards (bollette, economia, food)
over MQTT discovery. LARIA replaces HARIA, so those dashboards keep working only
if LARIA republishes the *same* entities. Home Assistant keys an MQTT entity by
its ``unique_id``: publish discovery with HARIA's unique_id and HA maps it onto
the existing entity, preserving its entity_id and every dashboard reference. So
this module mirrors HARIA's unique_ids, state topics, attribute topics, and
attribute keys verbatim. The payload building is pure and tested; the broker IO
lives in ``MqttMirror.publish_messages``.

This is deliberately separate from ``mqtt.py``, which publishes LARIA's own
namespaced (``laria_``) sensors. That path stays for anyone starting fresh; this
one exists to adopt an existing HARIA install.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from ...services.macros import compute_macro_targets
from ...storage import finance, food, mqtt_topics, utilities

# HA discovery config topics hang off this by convention; overridable per install
# but HARIA always used the standard root, so its entities live under it.
_STATE_FOOD = "haria/food"
_STATE_BOLL = "haria/bollette"
_STATE_ECON = "haria/economia"

_DEVICE_FOOD = {"identifiers": ["haria_cibo"], "name": "HARIA Cibo",
                "manufacturer": "HARIA", "model": "food_diary"}
_DEVICE_BOLL = {"identifiers": ["haria_bollette"], "name": "HARIA Bollette",
                "manufacturer": "HARIA", "model": "bollette"}
_DEVICE_ECON = {"identifiers": ["haria_economia"], "name": "HARIA Economia",
                "manufacturer": "HARIA", "model": "economia"}

# Meals sort into this order within a day, matching HARIA's dashboards.
_MEAL_ORDER = {"colazione": 0, "pranzo": 1, "snack": 2, "cena": 3}


def _slug(text: str) -> str:
    """HARIA's object_id/topic slug: lowercase, non-alphanumerics to underscore."""
    return re.sub(r"[^a-z0-9_]+", "_", (text or "").strip().lower()).strip("_")


@dataclass
class CompatSensor:
    """One HA sensor to publish with HARIA's exact identity.

    ``uid`` is the unique_id HA keys on (so it lands on the existing entity).
    ``attr_topic``/``attr`` are set only for the sensors that carry a JSON
    attributes payload (plans, breakdowns, lists).
    """
    uid: str
    name: str
    device: dict
    state_topic: str
    value: object = ""
    object_id: str | None = None
    unit: str = ""
    icon: str | None = None
    state_class: str | None = None
    device_class: str | None = None
    attr_topic: str | None = None
    attr: object = None


def discovery_config(sensor: CompatSensor, discovery_prefix: str) -> tuple[str, dict]:
    """Build the (config_topic, config) for one sensor's discovery message."""
    config: dict = {
        "name": sensor.name,
        "unique_id": sensor.uid,
        "state_topic": sensor.state_topic,
        "device": sensor.device,
    }
    if sensor.object_id:
        config["object_id"] = sensor.object_id
    if sensor.unit:
        config["unit_of_measurement"] = sensor.unit
    if sensor.icon:
        config["icon"] = sensor.icon
    if sensor.state_class:
        config["state_class"] = sensor.state_class
    if sensor.device_class:
        config["device_class"] = sensor.device_class
    if sensor.attr_topic:
        config["json_attributes_topic"] = sensor.attr_topic
    return f"{discovery_prefix}/sensor/{sensor.uid}/config", config


def state_messages(sensor: CompatSensor) -> list[tuple[str, object]]:
    """The (topic, payload) pairs carrying this sensor's state and attributes."""
    messages: list[tuple[str, object]] = [(sensor.state_topic, sensor.value)]
    if sensor.attr_topic is not None:
        messages.append((sensor.attr_topic, sensor.attr if sensor.attr is not None else {}))
    return messages


def _month_bounds(today: date) -> tuple[str, str, int, int]:
    """(first ISO, last ISO, year, month) of ``today``'s month."""
    first = today.replace(day=1)
    nxt = (first.replace(year=first.year + 1, month=1)
           if first.month == 12 else first.replace(month=first.month + 1))
    last = nxt - timedelta(days=1)
    return first.isoformat(), last.isoformat(), today.year, today.month


def _prev_month_bounds(today: date) -> tuple[str, str]:
    """(first ISO, last ISO) of the month before ``today``."""
    prev_last = today.replace(day=1) - timedelta(days=1)
    return prev_last.replace(day=1).isoformat(), prev_last.isoformat()


def _week_days(today: date) -> list[date]:
    """Monday to Sunday of ``today``'s week."""
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def _month_days(today: date) -> list[date]:
    """Every day of ``today``'s month."""
    first_iso, last_iso, _, _ = _month_bounds(today)
    first, last = date.fromisoformat(first_iso), date.fromisoformat(last_iso)
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


# ---------------------------------------------------------------- bollette

async def collect_bollette(today: date | None = None) -> list[CompatSensor]:
    """One sensor per (utility, metric, year), state = the 12 month CSV.

    Years are padded to a rolling three year window so a dashboard's year card
    never shows "unavailable" for a year with no data yet (the CSV is zeros).
    """
    today = today or date.today()
    sensors: list[CompatSensor] = []
    for utility, metric in await utilities.list_bill_series():
        years = set(await utilities.get_bill_years(utility, metric))
        years |= {today.year, today.year - 1, today.year - 2}
        for year in sorted(years):
            csv = await utilities.get_bill_csv(utility, metric, year)
            sensors.append(CompatSensor(
                uid=f"haria_boll_{utility}_{metric}_{year}",
                object_id=f"bollette_{utility}_{metric}_{year}",
                name=f"{utility} {metric} {year}",
                device=_DEVICE_BOLL,
                state_topic=f"{_STATE_BOLL}/{utility}/{metric}/{year}",
                value=csv,
            ))
    return sensors


# ---------------------------------------------------------------- economia

async def collect_economia(today: date | None = None) -> list[CompatSensor]:
    """Balances, monthly spending, budgets, goals, and the history matrices."""
    today = today or date.today()
    sensors: list[CompatSensor] = []
    sensors += await _balance_sensors()
    sensors += await _spending_sensors(today)
    sensors += await _budget_sensors(today)
    sensors += await _goal_sensors()
    sensors += await _history_sensors()
    return sensors


async def _balance_sensors() -> list[CompatSensor]:
    balances = await finance.get_balances()
    sensors: list[CompatSensor] = []
    total = 0.0
    per_owner: dict[str, float] = {}
    for row in balances:
        slug = _slug(row["account"])
        sensors.append(CompatSensor(
            uid=f"haria_econ_saldo_{slug}", object_id=f"economia_saldo_{slug}",
            name=f"Saldo {row['account'].capitalize()}", device=_DEVICE_ECON,
            state_topic=f"{_STATE_ECON}/saldo/{slug}", value=row["balance"],
            unit="€", icon="mdi:wallet", state_class="measurement",
        ))
        total += row["balance"]
        owner = row.get("owner") or "famiglia"
        per_owner[owner] = round(per_owner.get(owner, 0.0) + row["balance"], 2)
    sensors.append(CompatSensor(
        uid="haria_econ_saldo_totale", object_id="economia_saldo_totale",
        name="Saldo totale", device=_DEVICE_ECON,
        state_topic=f"{_STATE_ECON}/saldo_totale", value=round(total, 2),
        unit="€", icon="mdi:cash-multiple", state_class="measurement",
    ))
    for owner, value in per_owner.items():
        slug = _slug(owner)
        sensors.append(CompatSensor(
            uid=f"haria_econ_saldo_int_{slug}",
            object_id=f"economia_saldo_intestatario_{slug}",
            name=f"Saldo {owner.capitalize()}", device=_DEVICE_ECON,
            state_topic=f"{_STATE_ECON}/saldo_intestatario/{slug}", value=value,
            unit="€", icon="mdi:account-cash", state_class="measurement",
        ))
    return sensors


async def _spending_sensors(today: date) -> list[CompatSensor]:
    first, last, _, _ = _month_bounds(today)
    rep = await finance.expense_summary(date_from=first, date_to=last)
    # expenses are negative; show the amount spent. ``or 0.0`` collapses -0.0 (an
    # empty month) so the dashboard reads "0.0 €" rather than "-0.0 €".
    spent = round(-rep["expenses"], 2) or 0.0
    sensors = [CompatSensor(
        uid="haria_econ_spese_mese", object_id="economia_spese_mese",
        name="Spese mese", device=_DEVICE_ECON,
        state_topic=f"{_STATE_ECON}/spese_mese/state", value=spent, unit="€",
        icon="mdi:cart-arrow-down", attr_topic=f"{_STATE_ECON}/spese_mese/attr",
        attr={
            "entrate": rep["income"], "uscite": rep["expenses"], "netto": rep["net"],
            "per_categoria": {c["category"]: c["total"] for c in rep["by_category"]},
        },
    )]
    prev_first, prev_last = _prev_month_bounds(today)
    prev = await finance.expense_summary(date_from=prev_first, date_to=prev_last)
    spent_prev = round(-prev["expenses"], 2) or 0.0
    sensors.append(CompatSensor(
        uid="haria_econ_spese_mese_prec", object_id="economia_spese_mese_prec",
        name="Spese mese scorso", device=_DEVICE_ECON,
        state_topic=f"{_STATE_ECON}/spese_mese_prec", value=spent_prev, unit="€",
        icon="mdi:cart-outline",
    ))
    sensors.append(CompatSensor(
        uid="haria_econ_spese_mese_delta", object_id="economia_spese_mese_delta",
        name="Spese vs mese scorso", device=_DEVICE_ECON,
        state_topic=f"{_STATE_ECON}/spese_mese_delta",
        value=round(spent - spent_prev, 2) or 0.0, unit="€", icon="mdi:swap-vertical",
    ))
    return sensors


async def _budget_sensors(today: date) -> list[CompatSensor]:
    _, _, year, month = _month_bounds(today)
    sensors: list[CompatSensor] = []
    for b in await finance.get_budget_status(year, month):
        slug = _slug(b["category"])
        base = f"{_STATE_ECON}/budget/{slug}"
        sensors.append(CompatSensor(
            uid=f"haria_econ_budget_{slug}", object_id=f"economia_budget_{slug}",
            name=f"Budget {b['category']}", device=_DEVICE_ECON,
            state_topic=f"{base}/state", value=b["perc"], unit="%", icon="mdi:gauge",
            attr_topic=f"{base}/attr",
            attr={"budget": b["budget"], "speso": b["spent"],
                  "residuo": b["remaining"], "sforato": b["over"]},
        ))
    return sensors


async def _goal_sensors() -> list[CompatSensor]:
    sensors: list[CompatSensor] = []
    for g in await finance.get_goals():
        slug = _slug(g["name"])
        base = f"{_STATE_ECON}/obiettivo/{slug}"
        sensors.append(CompatSensor(
            uid=f"haria_econ_obiettivo_{slug}", object_id=f"economia_obiettivo_{slug}",
            name=f"Obiettivo {g['name']}", device=_DEVICE_ECON,
            state_topic=f"{base}/state", value=g["perc"], unit="%", icon="mdi:piggy-bank",
            attr_topic=f"{base}/attr",
            attr={
                "target": g["target"], "accantonato": g["saved"],
                "residuo": g["remaining"], "scadenza": g["target_date"] or "",
                "mesi_rimanenti": g["months_left"] if g["months_left"] is not None else "",
                "quota_mensile": g["monthly_quota"] if g["monthly_quota"] is not None else "",
                "raggiunto": g["reached"],
            },
        ))
    return sensors


async def _history_sensors() -> list[CompatSensor]:
    matrix = await finance.monthly_category_matrix()
    months, categories, totals = matrix["months"], matrix["categories"], matrix["totals"]
    averages = ({cat: round(sum(vals) / len(months), 2) for cat, vals in categories.items()}
                if months else {})
    history = CompatSensor(
        uid="haria_econ_storico", object_id="economia_storico_mensile",
        name="Spese storico mensile", device=_DEVICE_ECON,
        state_topic=f"{_STATE_ECON}/storico/state", value=len(months),
        icon="mdi:table-large", attr_topic=f"{_STATE_ECON}/storico/attr",
        attr={"mesi": months, "categorie": categories, "totali": totals, "medie": averages},
    )
    transactions = await finance.recent_transactions()
    moves = [{"d": t["date"], "i": t["amount"], "c": t["category"],
              "n": (t["description"] or "").strip()[:32]} for t in transactions]
    movements = CompatSensor(
        uid="haria_econ_movimenti", object_id="economia_movimenti",
        name="Movimenti recenti", device=_DEVICE_ECON,
        state_topic=f"{_STATE_ECON}/movimenti/state", value=len(moves),
        icon="mdi:format-list-bulleted", attr_topic=f"{_STATE_ECON}/movimenti/attr",
        attr={"movimenti": moves},
    )
    return [history, movements]


# ---------------------------------------------------------------- food

def _fmt_plan_item(entry: dict) -> str:
    """A planned meal as text: prefix the member when it is a personal override."""
    who = (entry.get("member") or "").strip()
    text = f"{who.capitalize()}: {entry['items']}" if who else entry["items"]
    if entry.get("kcal"):
        text += f" ({round(entry['kcal'])} kcal)"
    return text


def _fmt_shopping(item: dict) -> str:
    text = f"{item['name']} {item.get('qty') or ''}".strip()
    if item.get("price") is not None:
        text += f" — €{item['price']:.2f}"
    return text


def _fmt_pantry(item: dict) -> str:
    text = f"{item['name']} {item.get('qty') or ''}".strip()
    if item.get("expires_on"):
        text += f" (scad. {item['expires_on']})"
    return text


def _plan_by_day(plan: list[dict], days: list[date]) -> dict[str, str]:
    """Map each day (ISO) to its meals as ``"meal_type: item; ..."``, sorted."""
    grouped: dict[str, list[dict]] = {}
    for entry in plan:
        grouped.setdefault(entry["date"], []).append(entry)
    result: dict[str, str] = {}
    for day in days:
        iso = day.isoformat()
        meals = sorted(grouped.get(iso, []),
                       key=lambda x: (_MEAL_ORDER.get(x["meal_type"], 9), x.get("member") or ""))
        result[iso] = "; ".join(f"{m['meal_type']}: {_fmt_plan_item(m)}" for m in meals)
    return result


async def collect_food(today: date | None = None) -> list[CompatSensor]:
    """Per member nutrition and weight, plus the shared plan, shopping, and pantry.

    Food sensors carry no object_id (HARIA never set one); HA still keys on the
    unique_id, so the existing entities are matched all the same.
    """
    today = today or date.today()
    sensors: list[CompatSensor] = []
    for profile in await food.list_profiles():
        sensors += await _member_sensors(profile["member"], today)
    sensors += await _plan_sensors(today)
    sensors += await _shopping_pantry_sensors()
    return sensors


async def _member_sensors(member: str, today: date) -> list[CompatSensor]:
    slug = _slug(member)
    base = f"{_STATE_FOOD}/{slug}"
    cap = member.capitalize()
    today_iso = today.isoformat()

    totals = await food.get_day_totals(member, today_iso)
    hydration = await food.get_hydration_day(member, today_iso)
    profile = await food.get_profile(member)
    kcal_target = profile.get("kcal_target") if profile else None
    macros = compute_macro_targets(kcal_target, profile.get("weight_kg") if profile else None)
    stats = await food.get_weight_stats(member, 30)

    def sensor(suffix, name, value, unit="", icon=None, **extra):
        return CompatSensor(uid=f"haria_{slug}_{suffix}", name=f"{cap} {name}",
                            device=_DEVICE_FOOD, state_topic=f"{base}/{suffix}",
                            value=value, unit=unit, icon=icon, **extra)

    blank = ""
    sensors = [
        sensor("kcal_oggi", "kcal oggi", round(totals["kcal"]), "kcal", "mdi:fire"),
        sensor("kcal_target", "kcal target", kcal_target if kcal_target is not None else blank,
               "kcal", "mdi:target"),
        sensor("proteine_oggi", "proteine oggi", round(totals["protein_g"]), "g",
               "mdi:food-drumstick"),
        sensor("proteine_target", "proteine target",
               macros["protein_target_g"] if macros else blank, "g", "mdi:food-drumstick-outline"),
        sensor("carbo_oggi", "carboidrati oggi", round(totals["carbs_g"]), "g", "mdi:bread-slice"),
        sensor("carbo_target", "carboidrati target",
               macros["carbs_target_g"] if macros else blank, "g", "mdi:bread-slice-outline"),
        sensor("grassi_oggi", "grassi oggi", round(totals["fat_g"]), "g", "mdi:oil"),
        sensor("grassi_target", "grassi target",
               macros["fat_target_g"] if macros else blank, "g", "mdi:oil"),
        sensor("acqua_oggi", "acqua oggi", round(hydration["ml_total"]), "mL", "mdi:cup-water"),
    ]
    if stats:
        weight = stats["latest"]
        bmi = stats["latest_bmi"] if stats["latest_bmi"] is not None else (
            profile.get("bmi") if profile else None)
        sensors.append(sensor("peso_delta_30d", "peso Δ 30g", stats["delta"], "kg",
                              "mdi:scale-balance"))
        sensors.append(sensor("peso_min_30d", "peso min 30g", stats["min"], "kg",
                              "mdi:arrow-down-bold"))
        sensors.append(sensor("peso_max_30d", "peso max 30g", stats["max"], "kg",
                              "mdi:arrow-up-bold"))
    else:
        weight = profile.get("weight_kg") if profile else None
        bmi = profile.get("bmi") if profile else None
        sensors.append(sensor("peso_delta_30d", "peso Δ 30g", blank, "kg", "mdi:scale-balance"))
        sensors.append(sensor("peso_min_30d", "peso min 30g", blank, "kg", "mdi:arrow-down-bold"))
        sensors.append(sensor("peso_max_30d", "peso max 30g", blank, "kg", "mdi:arrow-up-bold"))
    sensors.append(sensor("peso", "peso", weight if weight is not None else blank, "kg",
                          "mdi:scale-bathroom", state_class="measurement", device_class="weight"))
    sensors.append(sensor("bmi", "BMI", bmi if bmi is not None else blank, icon="mdi:human",
                          state_class="measurement"))
    sensors.append(await _diary_sensor(member, slug, base, cap, today))
    return sensors


async def _diary_sensor(member: str, slug: str, base: str, cap: str,
                        today: date) -> CompatSensor:
    days = _week_days(today)
    meals = await food.get_meals(member, days[0].isoformat(), days[-1].isoformat())
    by_day: dict[str, list[dict]] = {}
    for meal in meals:
        by_day.setdefault((meal.get("eaten_at") or "")[:10], []).append(meal)
    attr: dict[str, str] = {}
    for day in days:
        iso = day.isoformat()
        ordered = sorted(by_day.get(iso, []),
                         key=lambda x: _MEAL_ORDER.get(x["meal_type"], 9))
        attr[iso] = "; ".join(
            f"{x['meal_type']}: {x['description']}"
            + (f" ({round(x['kcal_total'])} kcal)" if x.get("kcal_total") else "")
            for x in ordered
        )
    return CompatSensor(
        uid=f"haria_{slug}_diario_settimana", name=f"{cap} diario settimana",
        device=_DEVICE_FOOD, state_topic=f"{base}/diario_settimana/state",
        value=f"{len(meals)} pasti" if meals else "nessun pasto",
        icon="mdi:book-open-variant", attr_topic=f"{base}/diario_settimana/attr", attr=attr,
    )


async def _plan_sensors(today: date) -> list[CompatSensor]:
    today_iso = today.isoformat()
    day_plan = await food.get_meal_plan(today_iso, today_iso)
    day_plan.sort(key=lambda x: (_MEAL_ORDER.get(x["meal_type"], 9), x.get("member") or ""))
    day_attr: dict[str, str] = {}
    for meal_type in ("colazione", "pranzo", "snack", "cena"):
        group = [m for m in day_plan if m["meal_type"] == meal_type]
        if group:
            day_attr[meal_type] = "; ".join(_fmt_plan_item(m) for m in group)

    week_days = _week_days(today)
    week_plan = await food.get_meal_plan(week_days[0].isoformat(), week_days[-1].isoformat())
    month_days = _month_days(today)
    month_plan = await food.get_meal_plan(month_days[0].isoformat(), month_days[-1].isoformat())

    return [
        CompatSensor(uid="haria_piano_oggi", name="Piano oggi", device=_DEVICE_FOOD,
                     state_topic=f"{_STATE_FOOD}/piano_oggi/state",
                     value=f"{len(day_plan)} pasti" if day_plan else "nessun piano",
                     icon="mdi:silverware-fork-knife",
                     attr_topic=f"{_STATE_FOOD}/piano_oggi/attr", attr=day_attr),
        CompatSensor(uid="haria_piano_settimana", name="Piano settimana", device=_DEVICE_FOOD,
                     state_topic=f"{_STATE_FOOD}/piano_settimana/state",
                     value=f"{len(week_plan)} pasti", icon="mdi:calendar-week",
                     attr_topic=f"{_STATE_FOOD}/piano_settimana/attr",
                     attr=_plan_by_day(week_plan, week_days)),
        CompatSensor(uid="haria_piano_mese", name="Piano mese", device=_DEVICE_FOOD,
                     state_topic=f"{_STATE_FOOD}/piano_mese/state",
                     value=f"{len(month_plan)} pasti", icon="mdi:calendar-month",
                     attr_topic=f"{_STATE_FOOD}/piano_mese/attr",
                     attr=_plan_by_day(month_plan, month_days)),
    ]


async def _shopping_pantry_sensors() -> list[CompatSensor]:
    items = await food.get_shopping_list(include_checked=False)
    cost = await food.get_shopping_cost(include_checked=True)
    pantry = await food.get_pantry()
    expiring = await food.get_pantry_expiring(3)
    return [
        CompatSensor(uid="haria_spesa", name="Lista spesa", device=_DEVICE_FOOD,
                     state_topic=f"{_STATE_FOOD}/spesa/state", value=len(items), unit="voci",
                     icon="mdi:cart", attr_topic=f"{_STATE_FOOD}/spesa/attr",
                     attr={"voci": [_fmt_shopping(it) for it in items]}),
        CompatSensor(uid="haria_spesa_costo", name="Spesa costo", device=_DEVICE_FOOD,
                     state_topic=f"{_STATE_FOOD}/spesa_costo/state", value=cost["total"], unit="€",
                     icon="mdi:currency-eur", attr_topic=f"{_STATE_FOOD}/spesa_costo/attr",
                     attr={"voci_con_prezzo": cost["priced"], "voci_senza_prezzo": cost["missing"],
                           "voci_totali": cost["count"]}),
        CompatSensor(uid="haria_dispensa", name="Dispensa", device=_DEVICE_FOOD,
                     state_topic=f"{_STATE_FOOD}/dispensa/state", value=len(pantry), unit="voci",
                     icon="mdi:fridge", attr_topic=f"{_STATE_FOOD}/dispensa/attr",
                     attr={"voci": [_fmt_pantry(it) for it in pantry]}),
        CompatSensor(uid="haria_dispensa_scadenze", name="Dispensa in scadenza",
                     device=_DEVICE_FOOD, state_topic=f"{_STATE_FOOD}/dispensa_scadenze/state",
                     value=len(expiring), unit="voci", icon="mdi:clock-alert",
                     attr_topic=f"{_STATE_FOOD}/dispensa_scadenze/attr",
                     attr={"voci": [_fmt_pantry(it) for it in expiring]}),
    ]


# ---------------------------------------------------------------- publish

# Each kind is tracked separately so retiring one dashboard's entity never
# disturbs another's.
_COLLECTORS = {"bollette": collect_bollette, "economia": collect_economia, "food": collect_food}


async def publish_dashboards(mirror) -> None:
    """Publish every HARIA dashboard kind, retiring entities that vanished.

    Gathers sensors on the event loop, then runs the blocking publish in a worker
    thread. Meant to be scheduled periodically and triggered after a mutation.
    """
    import asyncio

    for kind, collect in _COLLECTORS.items():
        sensors = await collect()
        messages, published = _build_messages(sensors, mirror.discovery_prefix)
        messages += await _stale_messages(kind, published)
        if messages:
            await asyncio.to_thread(mirror.publish_messages, messages)
        await mqtt_topics.set_mqtt_topics(kind, published)


def _build_messages(sensors: list[CompatSensor],
                    discovery_prefix: str) -> tuple[list[tuple[str, object]], list[dict]]:
    """Discovery + state messages for the sensors, plus the topics to remember."""
    messages: list[tuple[str, object]] = []
    published: list[dict] = []
    for sensor in sensors:
        config_topic, config = discovery_config(sensor, discovery_prefix)
        messages.append((config_topic, config))
        state = state_messages(sensor)
        messages += state
        published.append({"config_topic": config_topic,
                          "state_topics": [topic for topic, _ in state]})
    return messages, published


async def _stale_messages(kind: str, published: list[dict]) -> list[tuple[str, object]]:
    """Empty payloads that delete entities published last run but not this one."""
    current = {entry["config_topic"] for entry in published}
    messages: list[tuple[str, object]] = []
    for old in await mqtt_topics.get_mqtt_topics(kind):
        if old["config_topic"] not in current:
            messages.append((old["config_topic"], ""))
            messages += [(topic, "") for topic in old.get("state_topics", [])]
    return messages
