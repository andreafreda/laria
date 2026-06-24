"""Home Assistant connector: optional, additive HA integration.

LARIA runs fully without it. When HA is configured, the composition root builds
an ``HaClient`` and registers the HA tools so the assistant can read state and
control devices on any reachable Home Assistant.
"""
from __future__ import annotations

from .client import HaClient
from .tools import register_ha_tools

__all__ = ["HaClient", "register_ha_tools"]
