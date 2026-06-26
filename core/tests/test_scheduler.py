"""Scheduler tests: cron parsing and which jobs are accepted."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from laria.scheduler import Scheduler, _convert_day_of_week, cron_trigger


async def _noop(_payload: dict) -> None:
    return None


def _scheduler() -> Scheduler:
    return Scheduler(on_reminder=_noop, on_briefing=_noop)


def test_convert_day_of_week_maps_unix_numbers():
    assert _convert_day_of_week("5") == "fri"
    assert _convert_day_of_week("0") == "sun"
    assert _convert_day_of_week("7") == "sun"
    assert _convert_day_of_week("*") == "*"
    assert _convert_day_of_week("1,3,5") == "mon,wed,fri"


def test_cron_trigger_requires_five_fields():
    with pytest.raises(ValueError):
        cron_trigger("0 8 * *")


def test_cron_trigger_accepts_standard_expression():
    trigger = cron_trigger("30 8 * * 1")
    assert trigger is not None


def test_schedule_reminder_rejects_past_one_shot():
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    accepted = _scheduler().schedule_reminder(
        {"id": 1, "message": "x", "remind_at": past, "recurring": None})
    assert accepted is False


def test_schedule_reminder_accepts_future_one_shot():
    future = (datetime.now() + timedelta(hours=1)).isoformat()
    accepted = _scheduler().schedule_reminder(
        {"id": 2, "message": "x", "remind_at": future, "recurring": None})
    assert accepted is True


def test_schedule_reminder_rejects_bad_cron():
    accepted = _scheduler().schedule_reminder(
        {"id": 3, "message": "x", "remind_at": None, "recurring": "nonsense"})
    assert accepted is False


def test_schedule_briefing_rejects_bad_cron():
    accepted = _scheduler().schedule_briefing({"id": 1, "cron": "bad"})
    assert accepted is False


def test_schedule_briefing_accepts_valid_cron():
    accepted = _scheduler().schedule_briefing({"id": 2, "cron": "0 8 * * *"})
    assert accepted is True
