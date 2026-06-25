"""Identity storage tests on a temp DB (no network)."""
from __future__ import annotations

import os

import pytest

from laria.config import reload_settings
from laria.storage import identity, init_db


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


async def test_profile_crud(db):
    pid = await identity.create_profile("Alice")
    again = await identity.create_profile("Alice")  # idempotent on name
    assert pid == again
    assert (await identity.get_profile("Alice"))["is_dependent"] is False
    assert [p["name"] for p in await identity.list_profiles()] == ["Alice"]


async def test_user_create_and_lookup(db):
    pid = await identity.create_profile("Alice")
    uid = await identity.create_user("alice", "hash", role="owner", profile_id=pid)
    user = await identity.get_user_by_username("alice")
    assert user["id"] == uid and user["role"] == "owner"
    assert user["profile_id"] == pid
    assert (await identity.get_user_by_id(uid))["username"] == "alice"
    assert await identity.count_users() == 1


async def test_set_password_and_must_change(db):
    uid = await identity.create_user("bob", "old")
    await identity.set_password(uid, "temp", must_change=True)
    user = await identity.get_user_by_id(uid)
    assert user["password_hash"] == "temp"
    assert user["must_change_password"] is True


async def test_telegram_link_and_lookup(db):
    uid = await identity.create_user("carol", "h")
    await identity.link_telegram(uid, "12345")
    found = await identity.get_user_by_telegram("12345")
    assert found["id"] == uid


async def test_guardianship(db):
    child = await identity.create_profile("Kid", is_dependent=True)
    parent_uid = await identity.create_user("parent", "h")
    await identity.add_guardianship(parent_uid, child)
    await identity.add_guardianship(parent_uid, child)  # idempotent
    assert await identity.list_wards(parent_uid) == [child]
    assert await identity.is_guardian(parent_uid, child) is True
    assert await identity.is_guardian(parent_uid, 999) is False
