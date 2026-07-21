"""Shared building blocks for the MQTT dashboard publishers.

Both the LARIA-native publisher (``dashboards.py``) and, during the migration
window, the HARIA-compat publisher (``compat.py``) turn a list of sensors into
retained MQTT discovery + state messages, and retire entities that vanished
between runs. That machinery is naming agnostic, so it lives here; each publisher
only supplies its own collectors (which ids, names, devices, and attributes to
emit). The payload building is pure and unit tested; broker IO stays in
``MqttMirror.publish_messages``.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date, timedelta

from ...storage import mqtt_topics

# Meals sort into this order within a day (matches the dashboards' expectations).
MEAL_ORDER = {"colazione": 0, "pranzo": 1, "snack": 2, "cena": 3}


def slug(text: str) -> str:
    """Lowercase, non-alphanumerics to underscore: a safe entity_id fragment."""
    return re.sub(r"[^a-z0-9_]+", "_", (text or "").strip().lower()).strip("_")


@dataclass
class Sensor:
    """One HA sensor to publish.

    ``uid`` is the unique_id HA keys the entity on. ``attr_topic``/``attr`` are
    set only for sensors carrying a JSON attributes payload (plans, breakdowns,
    lists).
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


def discovery_config(sensor: Sensor, discovery_prefix: str) -> tuple[str, dict]:
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


def state_messages(sensor: Sensor) -> list[tuple[str, object]]:
    """The (topic, payload) pairs carrying this sensor's state and attributes."""
    messages: list[tuple[str, object]] = [(sensor.state_topic, sensor.value)]
    if sensor.attr_topic is not None:
        messages.append((sensor.attr_topic, sensor.attr if sensor.attr is not None else {}))
    return messages


# ---------------------------------------------------------------- date helpers

def month_bounds(today: date) -> tuple[str, str, int, int]:
    """(first ISO, last ISO, year, month) of ``today``'s month."""
    first = today.replace(day=1)
    nxt = (first.replace(year=first.year + 1, month=1)
           if first.month == 12 else first.replace(month=first.month + 1))
    return first.isoformat(), (nxt - timedelta(days=1)).isoformat(), today.year, today.month


def prev_month_bounds(today: date) -> tuple[str, str]:
    """(first ISO, last ISO) of the month before ``today``."""
    prev_last = today.replace(day=1) - timedelta(days=1)
    return prev_last.replace(day=1).isoformat(), prev_last.isoformat()


def week_days(today: date) -> list[date]:
    """Monday to Sunday of ``today``'s week."""
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def month_days(today: date) -> list[date]:
    """Every day of ``today``'s month."""
    first_iso, last_iso, _, _ = month_bounds(today)
    first, last = date.fromisoformat(first_iso), date.fromisoformat(last_iso)
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


# ---------------------------------------------------------------- text helpers

def fmt_plan_item(entry: dict) -> str:
    """A planned meal as text: prefix the member when it is a personal override."""
    who = (entry.get("member") or "").strip()
    text = f"{who.capitalize()}: {entry['items']}" if who else entry["items"]
    if entry.get("kcal"):
        text += f" ({round(entry['kcal'])} kcal)"
    return text


def fmt_shopping(item: dict) -> str:
    text = f"{item['name']} {item.get('qty') or ''}".strip()
    if item.get("price") is not None:
        text += f" — €{item['price']:.2f}"
    return text


def fmt_pantry(item: dict) -> str:
    text = f"{item['name']} {item.get('qty') or ''}".strip()
    if item.get("expires_on"):
        text += f" (scad. {item['expires_on']})"
    return text


def plan_by_day(plan: list[dict], days: list[date]) -> dict[str, str]:
    """Map each day (ISO) to its meals as ``"meal_type: item; ..."``, sorted."""
    grouped: dict[str, list[dict]] = {}
    for entry in plan:
        grouped.setdefault(entry["date"], []).append(entry)
    result: dict[str, str] = {}
    for day in days:
        iso = day.isoformat()
        meals = sorted(grouped.get(iso, []),
                       key=lambda x: (MEAL_ORDER.get(x["meal_type"], 9), x.get("member") or ""))
        result[iso] = "; ".join(f"{m['meal_type']}: {fmt_plan_item(m)}" for m in meals)
    return result


# ---------------------------------------------------------------- publish

def build_messages(sensors: list[Sensor],
                   discovery_prefix: str) -> tuple[list[tuple[str, object]], list[dict]]:
    """Discovery + state messages for the sensors, plus the topics to remember."""
    messages: list[tuple[str, object]] = []
    published: list[dict] = []
    for sensor in sensors:
        config_topic, config = discovery_config(sensor, discovery_prefix)
        messages.append((config_topic, config))
        states = state_messages(sensor)
        messages += states
        published.append({"config_topic": config_topic,
                          "state_topics": [topic for topic, _ in states]})
    return messages, published


async def stale_messages(kind: str, published: list[dict]) -> list[tuple[str, object]]:
    """Empty payloads that delete entities published last run but not this one."""
    current = {entry["config_topic"] for entry in published}
    messages: list[tuple[str, object]] = []
    for old in await mqtt_topics.get_mqtt_topics(kind):
        if old["config_topic"] not in current:
            messages.append((old["config_topic"], ""))
            messages += [(topic, "") for topic in old.get("state_topics", [])]
    return messages


async def publish_kinds(mirror, collectors: dict) -> None:
    """Publish every dashboard kind, retiring entities that vanished.

    ``collectors`` maps a kind name to an async function returning its sensors.
    Gathers on the event loop, then runs the blocking publish in a worker thread.
    """
    for kind, collect in collectors.items():
        sensors = await collect()
        messages, published = build_messages(sensors, mirror.discovery_prefix)
        messages += await stale_messages(kind, published)
        if messages:
            await asyncio.to_thread(mirror.publish_messages, messages)
        await mqtt_topics.set_mqtt_topics(kind, published)
