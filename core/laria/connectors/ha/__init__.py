"""Home Assistant connector: optional, additive HA integration.

LARIA runs fully without it. When HA is configured, the composition root builds
an ``HaClient`` and registers the HA tools so the assistant can read state and
control devices on any reachable Home Assistant.
"""
from __future__ import annotations

from .agenda_tools import register_ha_agenda_tools
from .client import HaClient
from .dashboards import publish_native
from .mqtt import MqttMirror
from .tools import register_ha_tools

__all__ = ["HaClient", "register_ha_tools", "register_ha_agenda_tools",
           "MqttMirror", "publish_native"]
