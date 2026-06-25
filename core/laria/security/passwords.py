"""Password hashing with the standard library (no external dependency).

Uses PBKDF2-HMAC-SHA256 with a per-password random salt. The hash is stored as a
single self-describing string, ``pbkdf2_sha256$iterations$salt$hash``, so the
parameters travel with the value and can be raised over time without breaking
existing hashes.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 600_000  # OWASP-style cost for PBKDF2-SHA256
_SALT_BYTES = 16


def hash_password(plain: str, *, iterations: int = _ITERATIONS) -> str:
    """Hash a plaintext password into a storable, self-describing string."""
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return f"{_ALGORITHM}${iterations}${_b64(salt)}${_b64(derived)}"


def verify_password(plain: str, stored: str) -> bool:
    """Check a plaintext password against a stored hash.

    Returns False (rather than raising) on any malformed or unknown-format hash,
    so a corrupt value can never be mistaken for a match. The comparison is
    constant-time.
    """
    try:
        algorithm, iterations, salt_b64, hash_b64 = stored.split("$")
    except (ValueError, AttributeError):
        return False
    if algorithm != _ALGORITHM:
        return False
    salt = _unb64(salt_b64)
    expected = _unb64(hash_b64)
    derived = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, int(iterations))
    return hmac.compare_digest(derived, expected)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)
