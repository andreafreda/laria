"""Signed tokens (JWT, HS256) with the standard library.

A small JWT implementation good enough for first-party auth: HMAC-SHA256 signed,
with issued-at and expiry claims. Kept tiny and dependency-free; swap for PyJWT
later if we need more of the spec (other algorithms, audience checks, and so on).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

_HEADER = {"alg": "HS256", "typ": "JWT"}


class TokenError(Exception):
    """Raised when a token is malformed, tampered with, or expired."""


def encode(claims: dict, secret: str, *, ttl_seconds: int) -> str:
    """Sign ``claims`` into a JWT that expires after ``ttl_seconds``.

    Adds ``iat`` (issued at) and ``exp`` (expiry) automatically; do not put a
    password or other secret in the claims, they are only signed, not encrypted.
    """
    issued_at = int(time.time())
    payload = {**claims, "iat": issued_at, "exp": issued_at + ttl_seconds}
    signing_input = f"{_b64(_HEADER)}.{_b64(payload)}"
    signature = _sign(signing_input, secret)
    return f"{signing_input}.{signature}"


def decode(token: str, secret: str) -> dict:
    """Verify a token's signature and expiry and return its claims.

    Raises TokenError on a malformed token, a bad signature, or an expired one,
    so callers treat any failure as "not authenticated".
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("malformed token")
    header_b64, payload_b64, signature = parts

    expected = _sign(f"{header_b64}.{payload_b64}", secret)
    if not hmac.compare_digest(signature, expected):
        raise TokenError("bad signature")

    payload = json.loads(_unb64(payload_b64))
    if payload.get("exp", 0) < int(time.time()):
        raise TokenError("expired token")
    return payload


def _sign(signing_input: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"),
                      hashlib.sha256).digest()
    return _b64url(digest)


def _b64(obj: dict) -> str:
    return _b64url(json.dumps(obj, separators=(",", ":")).encode("utf-8"))


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)
