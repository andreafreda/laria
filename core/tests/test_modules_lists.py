"""Generic list module tests: tools wired to storage, dispatched directly."""
from __future__ import annotations

import json
import os

import pytest

from laria.config import reload_settings
from laria.engine import ToolRegistry
from laria.engine.tools import ToolContext
from laria.memory import Scope
from laria.memory.fake import FakeBackend
from laria.modules import register_lists_tools
from laria.storage import init_db


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


def _ctx() -> ToolContext:
    return ToolContext(user_id="u1", memory=FakeBackend(), scope=Scope(user_id="u1"))


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_lists_tools(registry)
    return registry


async def test_tools_registered(db):
    names = {s["name"] for s in _registry().schemas()}
    assert {"create_list", "show_lists", "add_to_list", "show_list",
            "check_list_item", "remove_list_item"} <= names


async def test_add_creates_list_on_first_use(db):
    registry = _registry()
    await registry.dispatch("add_to_list", {"list": "Packing", "item": "passport"}, _ctx())
    items = json.loads(await registry.dispatch("show_list", {"list": "packing"}, _ctx()))
    assert items[0]["text"] == "passport"
    lists = json.loads(await registry.dispatch("show_lists", {}, _ctx()))
    assert lists[0]["name"] == "Packing"


async def test_check_and_remove_item(db):
    registry = _registry()
    await registry.dispatch("add_to_list", {"list": "todo", "item": "call bank"}, _ctx())

    checked = json.loads(await registry.dispatch(
        "check_list_item", {"list": "todo", "item": "call bank"}, _ctx()))
    assert checked["ok"] is True
    items = json.loads(await registry.dispatch("show_list", {"list": "todo"}, _ctx()))
    assert items[0]["checked"] is True

    await registry.dispatch("remove_list_item", {"list": "todo", "item": "call bank"}, _ctx())
    assert json.loads(await registry.dispatch("show_list", {"list": "todo"}, _ctx())) == []


async def test_unknown_list(db):
    result = await _registry().dispatch("show_list", {"list": "nope"}, _ctx())
    assert "not found" in result


class StubScheduler:
    def __init__(self):
        self.scheduled = []
        self.cancelled = []

    def schedule_reminder(self, reminder):
        self.scheduled.append(reminder)
        return True

    def cancel_reminder(self, reminder_id):
        self.cancelled.append(reminder_id)


async def test_due_date_creates_and_links_reminder(db):
    from laria.storage import misc
    scheduler = StubScheduler()
    registry = ToolRegistry()
    register_lists_tools(registry, scheduler)

    await registry.dispatch(
        "add_to_list", {"list": "todo", "item": "pay rent", "due_at": "2099-01-01 09:00"}, _ctx())

    assert len(scheduler.scheduled) == 1
    reminders = await misc.get_user_reminders("u1")
    assert reminders[0]["message"] == "todo: pay rent"
    items = json.loads(await registry.dispatch("show_list", {"list": "todo"}, _ctx()))
    assert items[0]["reminder_id"] == reminders[0]["id"]


async def test_removing_item_cancels_reminder(db):
    from laria.storage import misc
    scheduler = StubScheduler()
    registry = ToolRegistry()
    register_lists_tools(registry, scheduler)
    await registry.dispatch(
        "add_to_list", {"list": "todo", "item": "pay rent", "due_at": "2099-01-01 09:00"}, _ctx())
    reminder_id = (await misc.get_user_reminders("u1"))[0]["id"]

    await registry.dispatch("remove_list_item", {"list": "todo", "item": "pay rent"}, _ctx())

    assert reminder_id in scheduler.cancelled
    assert await misc.get_user_reminders("u1") == []
