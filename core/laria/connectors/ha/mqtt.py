"""Mirror LARIA data into Home Assistant via MQTT discovery.

So existing Lovelace cards keep working: LARIA publishes its finance figures as HA
sensors. Every entity is namespaced by a configurable node id (default "laria"),
so it never collides with another publisher (such as HARIA) on the same broker.

The payload building is pure and tested; the broker IO is a thin wrapper around
paho-mqtt, imported lazily so the dependency is only needed when mirroring is on.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ...config import HASettings, get_settings
from ...storage import finance


@dataclass
class Sensor:
    """One value to expose as an HA sensor.

    ``object_id`` is the stable per-sensor slug; ``device_class`` (e.g.
    "monetary") lets HA format and group the value sensibly.
    """
    object_id: str
    name: str
    value: float | str
    unit: str = ""
    device_class: str | None = None


def slugify(text: str) -> str:
    """Turn an account or goal name into a safe MQTT/entity object_id fragment."""
    return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_") or "x"


def discovery_payload(sensor: Sensor, node_id: str,
                      discovery_prefix: str) -> tuple[str, dict, str]:
    """Build the (config_topic, config, state_topic) for one sensor.

    The unique_id and object_id are prefixed with the node id, which is what
    keeps LARIA's entities separate from any other publisher on the broker. All
    sensors share one HA device so they group under a single "LARIA" device.
    """
    namespaced = f"{node_id}_{sensor.object_id}"
    base = f"{discovery_prefix}/sensor/{node_id}/{sensor.object_id}"
    state_topic = f"{base}/state"
    config = {
        "name": sensor.name,
        "unique_id": namespaced,
        "object_id": namespaced,
        "state_topic": state_topic,
        "device": {"identifiers": [node_id], "name": "LARIA", "manufacturer": "LARIA"},
    }
    if sensor.unit:
        config["unit_of_measurement"] = sensor.unit
    if sensor.device_class:
        config["device_class"] = sensor.device_class
    return f"{base}/config", config, state_topic


def balance_sensors(balances: list[dict]) -> list[Sensor]:
    """A monetary sensor per account balance."""
    return [
        Sensor(object_id=f"balance_{slugify(b['account'])}",
               name=f"Balance {b['account']}", value=b["balance"],
               unit="EUR", device_class="monetary")
        for b in balances
    ]


def goal_sensors(goals: list[dict]) -> list[Sensor]:
    """A monetary sensor per savings goal (the amount saved so far)."""
    return [
        Sensor(object_id=f"goal_{slugify(g['name'])}",
               name=f"Goal {g['name']}", value=g["saved"],
               unit="EUR", device_class="monetary")
        for g in goals
    ]


async def collect_finance_sensors() -> list[Sensor]:
    """Gather the finance sensors LARIA currently mirrors (balances and goals)."""
    sensors = balance_sensors(await finance.get_balances())
    sensors += goal_sensors(await finance.get_goals())
    return sensors


class MqttMirror:
    """Publishes sensors to an MQTT broker using HA discovery (retained)."""

    def __init__(self, settings: HASettings | None = None):
        self._ha = settings or get_settings().ha

    def publish(self, sensors: list[Sensor]) -> None:
        """Publish discovery configs and current states for the given sensors.

        Synchronous (paho is blocking); call via ``asyncio.to_thread`` from async
        code. Imports paho-mqtt lazily so it is only required when mirroring runs.
        """
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "MQTT mirror needs the optional 'paho-mqtt' package."
            ) from exc

        client = mqtt.Client()
        if self._ha.mqtt_username:
            client.username_pw_set(self._ha.mqtt_username, self._ha.mqtt_password)
        client.connect(self._ha.mqtt_host, self._ha.mqtt_port)
        client.loop_start()
        try:
            for sensor in sensors:
                config_topic, config, state_topic = discovery_payload(
                    sensor, self._ha.mqtt_node_id, self._ha.mqtt_discovery_prefix)
                client.publish(config_topic, json.dumps(config), retain=True)
                client.publish(state_topic, sensor.value, retain=True)
        finally:
            client.loop_stop()
            client.disconnect()
