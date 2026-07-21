"""HARIA compatible MQTT publisher tests: pure builders, collectors, cleanup.

No broker: the mirror is a fake that records messages. The point of the compat
publisher is that its identifiers match HARIA's exactly, so the assertions pin
the unique_ids and topics HARIA used.
"""
from __future__ import annotations

import os
from datetime import date

import pytest

from laria.config import reload_settings
from laria.connectors.ha import compat
from laria.storage import finance, food, mqtt_topics, init_db, utilities


# ---------------------------------------------------------------- pure builders

def test_slug_matches_haria():
    assert compat._slug("Conto Corrente") == "conto_corrente"
    assert compat._slug("Luce/Gas!") == "luce_gas"


def test_discovery_config_uses_unique_id_as_key():
    sensor = compat.CompatSensor(
        uid="haria_boll_luce_kwh_2026", object_id="bollette_luce_kwh_2026",
        name="luce kwh 2026", device=compat._DEVICE_BOLL,
        state_topic="haria/bollette/luce/kwh/2026", value="1,2,3")
    config_topic, config = compat.discovery_config(sensor, "homeassistant")

    assert config_topic == "homeassistant/sensor/haria_boll_luce_kwh_2026/config"
    assert config["unique_id"] == "haria_boll_luce_kwh_2026"
    assert config["object_id"] == "bollette_luce_kwh_2026"
    assert config["state_topic"] == "haria/bollette/luce/kwh/2026"
    assert config["device"]["identifiers"] == ["haria_bollette"]


def test_state_messages_include_attributes_when_present():
    plain = compat.CompatSensor(uid="u", name="n", device={}, state_topic="s", value=5)
    assert compat.state_messages(plain) == [("s", 5)]

    rich = compat.CompatSensor(uid="u", name="n", device={}, state_topic="s/state",
                               value=1, attr_topic="s/attr", attr={"k": "v"})
    assert compat.state_messages(rich) == [("s/state", 1), ("s/attr", {"k": "v"})]


def test_month_and_week_helpers():
    today = date(2026, 3, 15)
    first, last, year, month = compat._month_bounds(today)
    assert (first, last, year, month) == ("2026-03-01", "2026-03-31", 2026, 3)
    assert compat._prev_month_bounds(today) == ("2026-02-01", "2026-02-28")
    week = compat._week_days(today)
    assert week[0] == date(2026, 3, 9) and week[-1] == date(2026, 3, 15)
    assert len(compat._month_days(today)) == 31


def test_fmt_plan_item_prefixes_member_and_appends_kcal():
    assert compat._fmt_plan_item({"member": "andrea", "items": "pasta", "kcal": 600}) \
        == "Andrea: pasta (600 kcal)"
    assert compat._fmt_plan_item({"member": "", "items": "insalata"}) == "insalata"


# ---------------------------------------------------------------- collectors

class CapturingMirror:
    """Fake mirror: records published messages, no broker."""

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


async def test_collect_bollette_matches_haria_ids_and_pads_years(db):
    await utilities.set_bill("luce", "kwh", 2026, 1, 100.0)
    sensors = await compat.collect_bollette(date(2026, 7, 1))

    by_uid = {s.uid: s for s in sensors}
    assert "haria_boll_luce_kwh_2026" in by_uid
    # rolling three year window is always present, even without data
    assert "haria_boll_luce_kwh_2025" in by_uid
    assert "haria_boll_luce_kwh_2024" in by_uid
    s = by_uid["haria_boll_luce_kwh_2026"]
    assert s.object_id == "bollette_luce_kwh_2026"
    assert s.state_topic == "haria/bollette/luce/kwh/2026"
    assert s.value.startswith("100")  # month 1 valued, rest zero


async def test_collect_economia_has_balance_total_and_spending(db):
    await finance.add_account("conto", "bank", opening_balance=500.0)
    await finance.add_transaction("conto", "2026-03-10", -40.0, "groceries", "spesa")
    await finance.set_goal("vacanza", 1000.0)
    sensors = await compat.collect_economia(date(2026, 3, 15))

    uids = {s.uid for s in sensors}
    assert "haria_econ_saldo_conto" in uids
    assert "haria_econ_saldo_totale" in uids
    assert "haria_econ_spese_mese" in uids
    assert "haria_econ_obiettivo_vacanza" in uids
    assert "haria_econ_storico" in uids and "haria_econ_movimenti" in uids

    spending = next(s for s in sensors if s.uid == "haria_econ_spese_mese")
    assert spending.value == 40.0  # absolute amount spent this month
    assert "per_categoria" in spending.attr


async def test_collect_food_globals_and_member(db):
    await food.upsert_profile("andrea", {"kcal_target": 2000, "weight_kg": 80.0})
    sensors = await compat.collect_food(date(2026, 3, 15))

    uids = {s.uid for s in sensors}
    # global sensors do not depend on any profile
    assert {"haria_piano_oggi", "haria_spesa", "haria_dispensa"} <= uids
    # member sensors carry no object_id but key on the unique_id
    assert "haria_andrea_kcal_oggi" in uids
    member = next(s for s in sensors if s.uid == "haria_andrea_kcal_oggi")
    assert member.object_id is None
    assert member.device["identifiers"] == ["haria_cibo"]


# ---------------------------------------------------------------- publish + cleanup

async def test_publish_dashboards_records_topics(db):
    await utilities.set_bill("gas", "m3", 2026, 2, 30.0)
    mirror = CapturingMirror()

    await compat.publish_dashboards(mirror)

    topics = {topic for topic, _ in mirror.messages}
    assert "homeassistant/sensor/haria_boll_gas_m3_2026/config" in topics
    stored = await mqtt_topics.get_mqtt_topics("bollette")
    assert any(e["config_topic"].endswith("haria_boll_gas_m3_2026/config") for e in stored)


async def test_publish_dashboards_retires_vanished_entity(db):
    # Pretend a utility series was published last run, then its data is gone.
    stale_config = "homeassistant/sensor/haria_boll_old_kwh_2020/config"
    await mqtt_topics.set_mqtt_topics("bollette", [
        {"config_topic": stale_config, "state_topics": ["haria/bollette/old/kwh/2020"]},
    ])
    mirror = CapturingMirror()

    await compat.publish_dashboards(mirror)

    cleared = [payload for topic, payload in mirror.messages if topic == stale_config]
    assert cleared == [""]  # config topic emptied so HA deletes the entity
