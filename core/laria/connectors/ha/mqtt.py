"""MQTT broker IO for the dashboard publisher.

A thin wrapper around paho-mqtt that publishes a batch of retained (topic,
payload) messages. The sensor model and payload building live in
``_mqtt_model.py``; this module is only the connection and write. paho-mqtt is
imported lazily so the dependency is only needed when publishing runs.
"""
from __future__ import annotations

import json

from ...config import HASettings, get_settings


class MqttMirror:
    """Publishes retained MQTT messages to the configured broker."""

    def __init__(self, settings: HASettings | None = None):
        self._ha = settings or get_settings().ha

    @property
    def discovery_prefix(self) -> str:
        """HA's MQTT discovery root; the publisher builds config topics on it."""
        return self._ha.mqtt_discovery_prefix

    def publish_messages(self, messages: list[tuple[str, object]]) -> None:
        """Publish a batch of (topic, payload) pairs, all retained.

        A dict or list payload is JSON encoded; anything else (number, string,
        or "" to clear a retained topic) is sent as is. Synchronous (paho is
        blocking); call via ``asyncio.to_thread`` from async code.
        """
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "MQTT publishing needs the 'paho-mqtt' package."
            ) from exc

        client = mqtt.Client()
        if self._ha.mqtt_username:
            client.username_pw_set(self._ha.mqtt_username, self._ha.mqtt_password)
        client.connect(self._ha.mqtt_host, self._ha.mqtt_port)
        client.loop_start()
        try:
            for topic, payload in messages:
                data = json.dumps(payload) if isinstance(payload, (dict, list)) else payload
                client.publish(topic, data, retain=True)
        finally:
            client.loop_stop()
            client.disconnect()
