"""HA agenda tool tests (to-do lists and calendar editing) with a stub client."""
from __future__ import annotations

import json

from laria.connectors.ha import register_ha_agenda_tools
from laria.engine import ToolRegistry
from laria.engine.tools import ToolContext
from laria.memory import Scope
from laria.memory.fake import FakeBackend


class StubHaClient:
    """A fake HaClient: canned states/events, records service and ws calls."""

    def __init__(self, states=None, events=None):
        self._states = states or []
        self._events = events or []
        self.service_calls: list[tuple] = []
        self.ws_calls: list[dict] = []

    async def get_states(self, entity_ids=None):
        return self._states

    async def call_service(self, domain, service, data, return_response=False):
        self.service_calls.append((domain, service, data))
        if return_response and service == "get_items":
            return {"service_response": {data["entity_id"]: {"items": self._events}}}
        return {"ok": True}

    async def get_calendar_events(self, calendar, start, end):
        return self._events

    async def ws_command(self, payload):
        self.ws_calls.append(payload)
        return {"success": True}


def _ctx() -> ToolContext:
    return ToolContext(user_id="u1", memory=FakeBackend(), scope=Scope(user_id="u1"))


def _registry(client) -> ToolRegistry:
    registry = ToolRegistry()
    register_ha_agenda_tools(registry, client)
    return registry


_TODO_STATE = [{"entity_id": "todo.house", "state": "0",
                "attributes": {"friendly_name": "House"}}]


async def test_agenda_tools_registered():
    names = {s["name"] for s in _registry(StubHaClient()).schemas()}
    assert {"list_todo_lists", "add_task", "get_tasks", "complete_task",
            "remove_task", "update_task", "delete_calendar_event",
            "update_calendar_event"} <= names


async def test_add_task_resolves_default_list():
    client = StubHaClient(states=_TODO_STATE)
    result = await _registry(client).dispatch("add_task", {"item": "milk"}, _ctx())
    assert json.loads(result)["ok"] is True
    domain, service, data = client.service_calls[0]
    assert (domain, service) == ("todo", "add_item")
    assert data == {"entity_id": "todo.house", "item": "milk"}


async def test_add_task_unknown_list():
    client = StubHaClient(states=_TODO_STATE)
    result = await _registry(client).dispatch(
        "add_task", {"item": "milk", "list": "garage"}, _ctx())
    assert "not found" in result


async def test_update_task_needs_a_change():
    client = StubHaClient(states=_TODO_STATE)
    result = await _registry(client).dispatch("update_task", {"item": "milk"}, _ctx())
    assert "Nothing to update" in result


async def test_delete_calendar_event_matches_title():
    client = StubHaClient(events=[
        {"summary": "Dentist", "uid": "u-1", "start": "2026-01-05", "end": "2026-01-05"},
        {"summary": "Lunch", "uid": "u-2", "start": "2026-01-06", "end": "2026-01-06"},
    ])
    result = await _registry(client).dispatch(
        "delete_calendar_event", {"calendar": "calendar.family", "title": "dentist"}, _ctx())
    assert json.loads(result)["deleted"] == 1
    assert client.ws_calls[0]["uid"] == "u-1"


async def test_update_calendar_event_fills_missing_fields():
    client = StubHaClient(events=[
        {"summary": "Dentist", "uid": "u-1", "start": "2026-01-05T09:00:00",
         "end": "2026-01-05T10:00:00"},
    ])
    await _registry(client).dispatch("update_calendar_event", {
        "calendar": "calendar.family", "title": "dentist", "new_title": "Dentist visit"}, _ctx())
    event = client.ws_calls[0]["event"]
    assert event["summary"] == "Dentist visit"
    assert event["dtstart"] == "2026-01-05T09:00:00"
