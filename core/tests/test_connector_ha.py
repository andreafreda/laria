"""Home Assistant connector tests with a stub client (no live HA)."""
from __future__ import annotations

import json

from laria.connectors.ha import register_ha_tools
from laria.engine import ToolRegistry
from laria.engine.tools import ToolContext
from laria.memory import Scope
from laria.memory.fake import FakeBackend


class StubHaClient:
    """A fake HaClient: canned states, records service calls, can be made to fail."""

    def __init__(self, states=None, fail=False):
        self._states = states or []
        self.fail = fail
        self.service_calls: list[tuple] = []

    async def get_states(self, entity_ids=None):
        if self.fail:
            raise ConnectionError("unreachable")
        if entity_ids:
            return [s for s in self._states if s["entity_id"] in entity_ids]
        return self._states

    async def call_service(self, domain, service, data, return_response=False):
        if self.fail:
            raise ConnectionError("unreachable")
        self.service_calls.append((domain, service, data))
        return {"ok": True}

    async def get_calendar_events(self, calendar, start, end):
        if self.fail:
            raise ConnectionError("unreachable")
        return [{"summary": "Dentist", "start": start, "end": end}]


def _ctx() -> ToolContext:
    return ToolContext(user_id="u1", memory=FakeBackend(), scope=Scope(user_id="u1"))


def _registry(client) -> ToolRegistry:
    registry = ToolRegistry()
    register_ha_tools(registry, client)
    return registry


async def test_ha_tools_registered():
    names = {s["name"] for s in _registry(StubHaClient()).schemas()}
    assert {"get_house_state", "control_device", "speak_alexa",
            "list_calendar_events", "create_calendar_event"} <= names


async def test_list_calendar_events():
    client = StubHaClient()
    result = await _registry(client).dispatch("list_calendar_events", {
        "calendar": "calendar.family", "start": "2026-01-01T00:00:00",
        "end": "2026-01-31T23:59:59"}, _ctx())
    events = json.loads(result)
    assert events[0]["summary"] == "Dentist"


async def test_create_calendar_event():
    client = StubHaClient()
    await _registry(client).dispatch("create_calendar_event", {
        "calendar": "calendar.family", "summary": "Lunch",
        "start": "2026-01-05T12:00:00", "end": "2026-01-05T13:00:00"}, _ctx())
    domain, service, data = client.service_calls[0]
    assert (domain, service) == ("calendar", "create_event")
    assert data["summary"] == "Lunch"


async def test_discovery_lists_entities():
    client = StubHaClient(states=[
        {"entity_id": "light.kitchen", "state": "on",
         "attributes": {"friendly_name": "Kitchen Light"}},
    ])
    result = await _registry(client).dispatch("get_house_state", {}, _ctx())
    discovery = json.loads(result)
    assert discovery == [{"entity_id": "light.kitchen", "name": "Kitchen Light"}]


async def test_read_specific_state():
    client = StubHaClient(states=[
        {"entity_id": "light.kitchen", "state": "on", "attributes": {}},
        {"entity_id": "light.hall", "state": "off", "attributes": {}},
    ])
    result = await _registry(client).dispatch(
        "get_house_state", {"entity_ids": ["light.hall"]}, _ctx())
    states = json.loads(result)
    assert len(states) == 1 and states[0]["state"] == "off"


async def test_control_device_calls_service():
    client = StubHaClient()
    await _registry(client).dispatch("control_device", {
        "domain": "light", "service": "turn_on", "data": {"entity_id": "light.kitchen"},
    }, _ctx())
    assert client.service_calls == [
        ("light", "turn_on", {"entity_id": "light.kitchen"})]


async def test_speak_alexa_uses_notify_service():
    client = StubHaClient()
    result = await _registry(client).dispatch("speak_alexa", {
        "media_player": "media_player.echo_kitchen", "message": "dinner is ready",
    }, _ctx())
    assert json.loads(result)["ok"] is True
    assert client.service_calls[0][:2] == ("notify", "alexa_media_echo_kitchen")


async def test_unreachable_ha_returns_message_not_crash():
    client = StubHaClient(fail=True)
    result = await _registry(client).dispatch("get_house_state", {}, _ctx())
    assert "Home Assistant error" in result
