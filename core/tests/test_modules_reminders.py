"""Reminder module tests: tools wired to storage, with a stub scheduler."""
from __future__ import annotations

import json
import os

import pytest

from laria.config import reload_settings
from laria.engine import ToolRegistry
from laria.engine.tools import ToolContext
from laria.memory import Scope
from laria.memory.fake import FakeBackend
from laria.modules import register_reminders_tools
from laria.storage import init_db


class StubScheduler:
    """Records scheduling calls so a test can assert on them without real timers."""

    def __init__(self, accept: bool = True):
        self.accept = accept
        self.scheduled: list[dict] = []
        self.cancelled: list[int] = []

    def schedule_reminder(self, reminder: dict) -> bool:
        self.scheduled.append(reminder)
        return self.accept

    def cancel_reminder(self, reminder_id: int) -> None:
        self.cancelled.append(reminder_id)


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
    return ToolContext(user_id="42", memory=FakeBackend(), scope=Scope(user_id="42"))


def _registry(scheduler) -> ToolRegistry:
    registry = ToolRegistry()
    register_reminders_tools(registry, scheduler)
    return registry


async def test_set_reminder_persists_and_schedules(db):
    scheduler = StubScheduler()
    registry = _registry(scheduler)

    result = await registry.dispatch(
        "set_reminder", {"message": "call mom", "recurring": "0 9 * * *"}, _ctx())

    assert "created" in result
    assert len(scheduler.scheduled) == 1
    listed = json.loads(await registry.dispatch("list_reminders", {}, _ctx()))
    assert listed[0]["message"] == "call mom"


async def test_set_reminder_requires_a_time(db):
    result = await _registry(StubScheduler()).dispatch(
        "set_reminder", {"message": "no time"}, _ctx())
    assert "Provide remind_at" in result


async def test_set_reminder_rolls_back_when_scheduler_rejects(db):
    scheduler = StubScheduler(accept=False)
    registry = _registry(scheduler)

    result = await registry.dispatch(
        "set_reminder", {"message": "x", "recurring": "0 9 * * *"}, _ctx())

    assert "invalid or in the past" in result
    listed = await registry.dispatch("list_reminders", {}, _ctx())
    assert listed == "No active reminders."


async def test_cancel_reminder(db):
    scheduler = StubScheduler()
    registry = _registry(scheduler)
    await registry.dispatch("set_reminder", {"message": "x", "recurring": "0 9 * * *"}, _ctx())
    listed = json.loads(await registry.dispatch("list_reminders", {}, _ctx()))
    reminder_id = listed[0]["id"]

    result = await registry.dispatch("cancel_reminder", {"id": reminder_id}, _ctx())

    assert "cancelled" in result
    assert reminder_id in scheduler.cancelled
    assert await registry.dispatch("list_reminders", {}, _ctx()) == "No active reminders."
