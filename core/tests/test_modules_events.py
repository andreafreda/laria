"""Recurring event tests: pure date logic + tools wired to storage."""
from __future__ import annotations

import json
import os
from datetime import date

import pytest

from laria.config import reload_settings
from laria.engine import ToolRegistry
from laria.engine.tools import ToolContext
from laria.memory import Scope
from laria.memory.fake import FakeBackend
from laria.modules import events as events_module
from laria.modules import register_events_tools
from laria.storage import init_db


def _event(month, day, notify_days_before=0, kind="birthday", label="x"):
    return {"month": month, "day": day, "notify_days_before": notify_days_before,
            "kind": kind, "label": label}


def test_due_on_the_day():
    e = _event(3, 12)
    assert events_module.is_due(e, date(2026, 3, 12)) is True
    assert events_module.is_due(e, date(2026, 3, 11)) is False


def test_notify_days_before_window():
    e = _event(3, 12, notify_days_before=3)
    assert events_module.is_due(e, date(2026, 3, 9)) is True   # 3 days before
    assert events_module.is_due(e, date(2026, 3, 8)) is False  # 4 days before
    assert events_module.days_until(e, date(2026, 3, 9)) == 3


def test_year_wrap():
    e = _event(1, 1)
    assert events_module.days_until(e, date(2026, 12, 31)) == 1


def test_leap_day_observed_on_28_in_non_leap_year():
    e = _event(2, 29)
    # 2026 is not a leap year -> observed on Feb 28
    assert events_module.days_until(e, date(2026, 2, 28)) == 0


def test_message_today_vs_future():
    e = _event(3, 12, kind="birthday", label="Marina")
    assert "today" in events_module.event_message(e, date(2026, 3, 12))
    assert "in 2 days" in events_module.event_message(e, date(2026, 3, 10))


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
    return ToolContext(user_id="7", memory=FakeBackend(), scope=Scope(user_id="7"))


async def test_add_list_delete_event(db):
    registry = ToolRegistry()
    register_events_tools(registry)

    created = json.loads(await registry.dispatch(
        "add_event", {"label": "Marina's birthday", "kind": "birthday",
                      "month": 3, "day": 12, "notify_days_before": 2}, _ctx()))
    assert created["ok"] is True
    event_id = created["event"]["id"]

    listed = json.loads(await registry.dispatch("list_events", {}, _ctx()))
    assert listed[0]["label"] == "Marina's birthday"

    await registry.dispatch("delete_event", {"id": event_id}, _ctx())
    assert await registry.dispatch("list_events", {}, _ctx()) == "No events yet."
