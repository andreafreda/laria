"""Authentication service: login, owner bootstrap, password change.

Ties together the identity storage and the security primitives. Channels and the
web API call this; they never touch password hashes or token internals directly.
See docs/design-auth.md for the model.
"""
from __future__ import annotations

import logging

from ..config import Settings, get_settings
from ..security import decode, encode, hash_password, verify_password
from ..storage import identity

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised when authentication or a token check fails."""


def issue_token(user: dict, settings: Settings | None = None) -> str:
    """Sign a login token carrying the user's identity and role.

    ``must_change`` rides along so the client can force a password change after a
    temporary password without an extra round trip.
    """
    s = settings or get_settings()
    claims = {
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"],
        "profile_id": user["profile_id"],
        "must_change": user["must_change_password"],
    }
    return encode(claims, s.auth.jwt_secret, ttl_seconds=s.auth.token_ttl_seconds)


def verify_token(token: str, settings: Settings | None = None) -> dict:
    """Return the claims of a valid token, or raise AuthError.

    Wraps the lower-level TokenError so callers depend only on this module.
    """
    s = settings or get_settings()
    try:
        return decode(token, s.auth.jwt_secret)
    except Exception as error:  # TokenError and any malformed input
        raise AuthError("invalid or expired token") from error


async def authenticate(username: str, password: str,
                       settings: Settings | None = None) -> str:
    """Verify credentials and return a login token, or raise AuthError.

    The same error is raised for an unknown user and a wrong password, so the
    response never reveals which usernames exist.
    """
    user = await identity.get_user_by_username(username)
    if user is None or not verify_password(password, user["password_hash"]):
        raise AuthError("invalid username or password")
    return issue_token(user, settings)


async def change_password(user_id: int, new_password: str) -> bool:
    """Set a new password and clear the must-change flag. False if no such user."""
    return await identity.set_password(
        user_id, hash_password(new_password), must_change=False)


async def create_user_account(username: str, password: str, *, role: str = "adult",
                              profile_id: int | None = None) -> int:
    """Create a login with a hashed password (admin action). Returns the user id."""
    return await identity.create_user(
        username, hash_password(password), role=role, profile_id=profile_id)


async def reset_password(user_id: int, new_password: str, *,
                         must_change: bool = True) -> bool:
    """Set a user's password as an admin; by default forces a change at next login."""
    return await identity.set_password(
        user_id, hash_password(new_password), must_change=must_change)


async def ensure_owner(settings: Settings | None = None) -> bool:
    """Create the owner from the admin seed on first run, once.

    Does nothing if any user already exists or the seed is not configured, so it
    is safe to call on every startup. Returns True only when it created the owner.
    """
    s = settings or get_settings()
    if not s.auth.admin_user or not s.auth.admin_password:
        return False
    if await identity.count_users() > 0:
        return False

    profile_id = await identity.create_profile(s.auth.admin_user)
    await identity.create_user(
        s.auth.admin_user, hash_password(s.auth.admin_password),
        role="owner", profile_id=profile_id)
    logger.info("created owner user '%s' from the admin seed", s.auth.admin_user)
    return True
