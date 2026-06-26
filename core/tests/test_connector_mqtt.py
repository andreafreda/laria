"""MQTT mirror tests: pure payload builders and namespacing (no broker)."""
from __future__ import annotations

import os

import pytest

from laria.config import reload_settings
from laria.connectors.ha.mqtt import (
    Sensor,
    balance_sensors,
    discovery_payload,
    goal_sensors,
    publish_finance,
    slugify,
)
from laria.storage import finance, init_db


def test_slugify():
    assert slugify("Checking Account") == "checking_account"
    assert slugify("PostePay #1!") == "postepay_1"
    assert slugify("   ") == "x"


def test_discovery_payload_is_namespaced():
    sensor = Sensor(object_id="balance_checking", name="Balance checking",
                    value=120.0, unit="EUR", device_class="monetary")
    config_topic, config, state_topic = discovery_payload(
        sensor, node_id="laria", discovery_prefix="homeassistant")

    assert config_topic == "homeassistant/sensor/laria/balance_checking/config"
    assert state_topic == "homeassistant/sensor/laria/balance_checking/state"
    # node id namespaces the entity so it never clashes with another publisher
    assert config["unique_id"] == "laria_balance_checking"
    assert config["object_id"] == "laria_balance_checking"
    assert config["device"]["identifiers"] == ["laria"]
    assert config["unit_of_measurement"] == "EUR"


def test_custom_node_id_changes_namespace():
    sensor = Sensor(object_id="balance_x", name="x", value=1)
    _, config, _ = discovery_payload(sensor, node_id="laria_test",
                                     discovery_prefix="homeassistant")
    assert config["unique_id"] == "laria_test_balance_x"


def test_balance_and_goal_sensors():
    balances = [{"account": "Checking", "balance": 120.0}]
    goals = [{"name": "Vacation", "saved": 250.0}]
    bs = balance_sensors(balances)
    gs = goal_sensors(goals)

    assert bs[0].object_id == "balance_checking" and bs[0].value == 120.0
    assert bs[0].device_class == "monetary"
    assert gs[0].object_id == "goal_vacation" and gs[0].value == 250.0


class CapturingMirror:
    """A fake MqttMirror that records what would be published, no broker."""

    def __init__(self):
        self.published: list = []

    def publish(self, sensors) -> None:
        self.published.extend(sensors)


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


async def test_publish_finance_mirrors_balances_and_goals(db):
    await finance.add_account("checking", "bank", opening_balance=120.0)
    await finance.set_goal("vacation", 1000.0)
    mirror = CapturingMirror()

    await publish_finance(mirror)

    object_ids = {s.object_id for s in mirror.published}
    assert "balance_checking" in object_ids
    assert "goal_vacation" in object_ids
