"""Home Assistant tools the assistant can call when the connector is enabled.

These are the additive, HA-specific tools (read entity state, control devices,
speak through Alexa). They live in the connector, not the core engine, so LARIA
runs fully without Home Assistant; the composition root registers them only when
HA is configured.

Each handler closes over an ``HaClient`` and turns connection or auth failures
into a short message the model can relay, rather than crashing the chat turn.
"""
from __future__ import annotations

import json
from typing import Any

from ...engine.tools import Tool, ToolContext, ToolRegistry
from .client import HaClient

# Failures worth turning into a readable result instead of aborting the turn.
_REACHABILITY_ERRORS = (ConnectionError, PermissionError, TimeoutError, RuntimeError)


def register_ha_tools(registry: ToolRegistry, client: HaClient) -> None:
    """Add the Home Assistant tools to a registry, bound to a live client."""

    async def get_house_state(inputs: dict[str, Any], ctx: ToolContext) -> str:
        """Discover entities or read live state.

        Without entity_ids: a slim list (entity_id and friendly name) to find the
        right entity. With entity_ids: the live state of those entities.
        """
        entity_ids = inputs.get("entity_ids") or None
        try:
            states = await client.get_states(entity_ids)
        except _REACHABILITY_ERRORS as error:
            return f"Home Assistant error: {error}"
        if entity_ids:
            return json.dumps(states, ensure_ascii=False)
        discovery = [
            {"entity_id": s["entity_id"],
             "name": s["attributes"].get("friendly_name", s["entity_id"])}
            for s in states
        ]
        return json.dumps(discovery, ensure_ascii=False)

    async def control_device(inputs: dict[str, Any], ctx: ToolContext) -> str:
        """Control a device by calling a Home Assistant service."""
        try:
            result = await client.call_service(
                inputs["domain"], inputs["service"], inputs.get("data", {}))
        except _REACHABILITY_ERRORS as error:
            return f"Home Assistant error: {error}"
        return json.dumps(result, ensure_ascii=False)

    async def speak_alexa(inputs: dict[str, Any], ctx: ToolContext) -> str:
        """Speak a message aloud on an Alexa/Echo device via its notify service.

        Tries an announcement first, then plain TTS, since not every device
        supports both.
        """
        media_player = inputs["media_player"]
        object_id = media_player.split(".", 1)[1] if "." in media_player else media_player
        notify_service = f"alexa_media_{object_id}"
        for announce_type in ("announce", "tts"):
            try:
                await client.call_service("notify", notify_service, {
                    "message": inputs["message"],
                    "data": {"type": announce_type},
                })
                return json.dumps({"ok": True, "mode": announce_type, "device": media_player})
            except _REACHABILITY_ERRORS:
                continue
        return json.dumps({"ok": False, "device": media_player,
                           "error": "could not reach the Alexa notify service"})

    registry.register(Tool(
        name="get_house_state",
        description=("Discover Home Assistant entities or read live state. Without "
                     "entity_ids: a list of entity_id plus friendly name to find "
                     "the right one. With entity_ids: the live state of those."),
        input_schema={
            "type": "object",
            "properties": {
                "entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "entity_ids to read live (e.g. light.kitchen); empty to discover",
                },
            },
        },
        handler=get_house_state,
    ))
    registry.register(Tool(
        name="control_device",
        description="Control a Home Assistant device by calling a service.",
        input_schema={
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "HA domain, e.g. light, switch, climate"},
                "service": {"type": "string", "description": "Service, e.g. turn_on, set_temperature"},
                "data": {"type": "object", "description": "Service data, e.g. {entity_id: light.kitchen}"},
            },
            "required": ["domain", "service", "data"],
        },
        handler=control_device,
    ))
    registry.register(Tool(
        name="speak_alexa",
        description=("Say a message aloud on an Alexa/Echo device. Use the Echo "
                     "media_player entity_id, found via get_house_state."),
        input_schema={
            "type": "object",
            "properties": {
                "media_player": {"type": "string", "description": "Echo media_player entity_id"},
                "message": {"type": "string", "description": "Text to speak"},
            },
            "required": ["media_player", "message"],
        },
        handler=speak_alexa,
    ))
