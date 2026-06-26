"""Generic lists storage tests on a temp DB (no network)."""
from __future__ import annotations

import os

import pytest

from laria.config import reload_settings
from laria.storage import init_db, lists


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


async def test_create_list_and_count_open_items(db):
    created = await lists.create_list("House todo", "todo")
    await lists.add_list_item(created["id"], "call plumber")
    await lists.add_list_item(created["id"], "pay tax", due_at="2026-06-30 09:00")

    all_lists = await lists.get_lists()
    assert len(all_lists) == 1
    assert all_lists[0]["name"] == "House todo"
    assert all_lists[0]["open_items"] == 2


async def test_unknown_kind_falls_back_to_todo(db):
    created = await lists.create_list("Random", "nonsense")
    assert created["kind"] == "todo"


async def test_toggle_item_updates_open_count(db):
    created = await lists.create_list("Groceries", "shopping")
    milk = await lists.add_list_item(created["id"], "milk", qty="1 L")
    await lists.add_list_item(created["id"], "bread")

    assert await lists.toggle_list_item(milk["id"]) is True
    assert (await lists.get_lists())[0]["open_items"] == 1

    items = await lists.get_list_items(created["id"])
    # Checked items sort after open ones.
    assert items[-1]["text"] == "milk" and items[-1]["checked"] is True


async def test_due_at_round_trips(db):
    created = await lists.create_list("Errands", "todo")
    await lists.add_list_item(created["id"], "call plumber", due_at="2026-06-27 09:00")
    item = (await lists.get_list_items(created["id"]))[0]
    assert item["due_at"] == "2026-06-27 09:00"


async def test_delete_list_removes_items(db):
    created = await lists.create_list("Temp", "checklist")
    await lists.add_list_item(created["id"], "x")
    assert await lists.delete_list(created["id"]) is True
    assert await lists.get_lists() == []


async def test_delete_item(db):
    created = await lists.create_list("Temp", "todo")
    item = await lists.add_list_item(created["id"], "x")
    assert await lists.delete_list_item(item["id"]) is True
    assert await lists.get_list_items(created["id"]) == []
