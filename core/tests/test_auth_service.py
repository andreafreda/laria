"""Auth service tests on a temp DB (no network)."""
from __future__ import annotations

import os

import pytest

from laria import auth
from laria.config import reload_settings
from laria.storage import identity, init_db


@pytest.fixture
async def db(tmp_path):
    os.environ["LARIA_DB_PATH"] = str(tmp_path / "test.db")
    os.environ["LARIA_DATA_DIR"] = str(tmp_path)
    os.environ["LARIA_JWT_SECRET"] = "test-secret"
    os.environ["LARIA_ADMIN_USER"] = "owner"
    os.environ["LARIA_ADMIN_PASSWORD"] = "owner-pass"
    reload_settings()
    await init_db()
    yield
    for key in ("LARIA_DB_PATH", "LARIA_DATA_DIR", "LARIA_JWT_SECRET",
                "LARIA_ADMIN_USER", "LARIA_ADMIN_PASSWORD"):
        os.environ.pop(key, None)
    reload_settings()


async def test_ensure_owner_creates_once(db):
    assert await auth.ensure_owner() is True
    assert await auth.ensure_owner() is False  # idempotent, user already exists
    user = await identity.get_user_by_username("owner")
    assert user["role"] == "owner" and user["profile_id"] is not None


async def test_authenticate_returns_valid_token(db):
    await auth.ensure_owner()
    token = await auth.authenticate("owner", "owner-pass")
    claims = auth.verify_token(token)
    assert claims["username"] == "owner" and claims["role"] == "owner"


async def test_authenticate_rejects_bad_credentials(db):
    await auth.ensure_owner()
    with pytest.raises(auth.AuthError):
        await auth.authenticate("owner", "wrong")
    with pytest.raises(auth.AuthError):
        await auth.authenticate("ghost", "whatever")


async def test_change_password(db):
    await auth.ensure_owner()
    uid = (await identity.get_user_by_username("owner"))["id"]
    await auth.change_password(uid, "new-pass")
    with pytest.raises(auth.AuthError):
        await auth.authenticate("owner", "owner-pass")
    assert await auth.authenticate("owner", "new-pass")


async def test_verify_token_rejects_garbage(db):
    with pytest.raises(auth.AuthError):
        auth.verify_token("not.a.token")
