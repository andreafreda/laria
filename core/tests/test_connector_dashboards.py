"""LARIA-native MQTT publisher tests: clean English entity model, no broker."""
from __future__ import annotations

import os
from datetime import date

import pytest

from laria.config import reload_settings
from laria.connectors.ha import dashboards as d
from laria.storage import finance, food, init_db, mqtt_topics, utilities


class CapturingMirror:
    discovery_prefix = "homeassistant"

    def __init__(self):
        self.messages: list = []

    def publish_messages(self, messages) -> None:
        self.messages.extend(messages)


@pytest.fixture
async def db(tmp_path):
    os.environ["LARIA_DB_PATH"] = str(tmp_path / "test.db")
    os.environ["LARIA_DATA_DIR"] = str(tmp_path)
    reload_settings()
    await init_db()
    yield
    os.environ.pop("LARIA_DB_PATH", None)
    os.environ.pop("LARIA_DATA_DIR", None)
    reload_settings()


def test_utility_english_mapping():
    assert d._utility_en("corrente") == "electricity"
    assert d._utility_en("acqua") == "water"
    assert d._utility_en("telefono") == "telefono"  # unknown -> slug
    assert d._metric_en("eur") == "cost"
    assert d._metric_en("kwh") == "kwh"


async def test_collect_utilities_uses_english_ids(db):
    await utilities.set_bill("corrente", "eur", 2026, 1, 88.0)
    sensors = await d.collect_utilities(date(2026, 7, 1))

    by_uid = {s.uid: s for s in sensors}
    assert "laria_utility_electricity_cost_2026" in by_uid
    s = by_uid["laria_utility_electricity_cost_2026"]
    assert s.object_id == "laria_utility_electricity_cost_2026"
    assert s.state_topic == "laria/utility/electricity/cost/2026"
    assert s.device["identifiers"] == ["laria_utilities"]
    assert s.value.startswith("88")


async def test_collect_finance_english_ids_and_attrs(db):
    await finance.add_account("conto", "bank", opening_balance=500.0)
    await finance.add_transaction("conto", "2026-03-10", -40.0, "groceries", "spesa")
    await finance.set_goal("vacanza", 1000.0)
    sensors = await d.collect_finance(date(2026, 3, 15))

    uids = {s.uid for s in sensors}
    assert {"laria_finance_total_balance", "laria_finance_balance_conto",
            "laria_finance_spending_month", "laria_finance_goal_vacanza",
            "laria_finance_spending_history", "laria_finance_recent_transactions"} <= uids

    spending = next(s for s in sensors if s.uid == "laria_finance_spending_month")
    assert spending.value == 40.0
    assert set(spending.attr) == {"income", "expenses", "net", "by_category"}

    txns = next(s for s in sensors if s.uid == "laria_finance_recent_transactions")
    assert txns.attr["transactions"][0]["category"] == "groceries"


async def test_collect_diet_english_ids(db):
    await food.upsert_profile("andrea", {"kcal_target": 2000, "weight_kg": 80.0})
    sensors = await d.collect_diet(date(2026, 3, 15))

    uids = {s.uid for s in sensors}
    assert {"laria_diet_plan_today", "laria_diet_shopping_list", "laria_diet_pantry"} <= uids
    assert "laria_diet_andrea_kcal_today" in uids
    member = next(s for s in sensors if s.uid == "laria_diet_andrea_kcal_today")
    assert member.device["identifiers"] == ["laria_diet"]

    shopping = next(s for s in sensors if s.uid == "laria_diet_shopping_list")
    assert "items" in shopping.attr


async def test_publish_native_records_topics_per_kind(db):
    await utilities.set_bill("gas", "m3", 2026, 2, 30.0)
    mirror = CapturingMirror()

    await d.publish_native(mirror)

    topics = {t for t, _ in mirror.messages}
    assert "homeassistant/sensor/laria_utility_gas_m3_2026/config" in topics
    stored = await mqtt_topics.get_mqtt_topics("utilities")
    assert any(e["config_topic"].endswith("laria_utility_gas_m3_2026/config") for e in stored)


async def test_publish_native_retires_vanished_entity(db):
    stale = "homeassistant/sensor/laria_utility_old_kwh_2020/config"
    await mqtt_topics.set_mqtt_topics("utilities", [
        {"config_topic": stale, "state_topics": ["laria/utility/old/kwh/2020"]}])
    mirror = CapturingMirror()

    await d.publish_native(mirror)

    cleared = [payload for topic, payload in mirror.messages if topic == stale]
    assert cleared == [""]
