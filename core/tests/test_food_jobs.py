"""Proactive food broadcast tests with a capturing Telegram client."""
from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

from laria.channels.food_jobs import FoodBroadcaster
from laria.config import reload_settings
from laria.security import hash_password
from laria.storage import food, identity, init_db


class CapturingClient:
    """Records every (chat_id, text) instead of calling Telegram."""

    def __init__(self):
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


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


async def _linked_user(name: str = "sam", chat_id: str = "555") -> None:
    profile_id = await identity.create_profile(name)
    await identity.create_user(name, hash_password("x"),
                               profile_id=profile_id, telegram_chat_id=chat_id)


async def test_daily_plan_broadcasts_today(db):
    await _linked_user()
    await food.set_plan_meal(date.today().isoformat(), "dinner", "pasta")
    client = CapturingClient()

    await FoodBroadcaster(client).daily_plan()

    assert len(client.sent) == 1
    chat_id, text = client.sent[0]
    assert chat_id == 555
    assert "pasta" in text


async def test_daily_plan_silent_when_empty(db):
    await _linked_user()
    client = CapturingClient()
    await FoodBroadcaster(client).daily_plan()
    assert client.sent == []


async def test_pantry_alert_lists_expiring(db):
    await _linked_user()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    await food.add_pantry_items([{"name": "milk", "expires_on": tomorrow}])
    client = CapturingClient()

    await FoodBroadcaster(client).pantry_alert()

    assert len(client.sent) == 1
    assert "milk" in client.sent[0][1]


async def test_weekly_report_uses_profile_member(db):
    await _linked_user(name="sam")
    await food.add_meal("sam", "lunch", "rice", {"kcal_total": 600}, [],
                        f"{date.today().isoformat()} 12:00:00", None)
    client = CapturingClient()

    await FoodBroadcaster(client).weekly_report()

    assert len(client.sent) == 1
    assert "Weekly report for Sam" in client.sent[0][1]
