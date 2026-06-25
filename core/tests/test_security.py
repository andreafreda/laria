"""Password hashing and token signing tests (pure, no DB, no network)."""
from __future__ import annotations

import time

import pytest

from laria.security import passwords, tokens


# --- passwords ---

def test_hash_is_not_plaintext_and_verifies():
    stored = passwords.hash_password("hunter2")
    assert stored != "hunter2"
    assert passwords.verify_password("hunter2", stored) is True
    assert passwords.verify_password("wrong", stored) is False


def test_same_password_hashes_differently():
    # random salt means two hashes of the same password never match byte for byte
    assert passwords.hash_password("x") != passwords.hash_password("x")


def test_malformed_hash_is_rejected():
    assert passwords.verify_password("x", "not-a-real-hash") is False
    assert passwords.verify_password("x", "") is False


# --- tokens ---

def test_encode_decode_roundtrip():
    token = tokens.encode({"sub": "alice", "role": "owner"}, "secret", ttl_seconds=60)
    claims = tokens.decode(token, "secret")
    assert claims["sub"] == "alice" and claims["role"] == "owner"
    assert "iat" in claims and "exp" in claims


def test_wrong_secret_fails():
    token = tokens.encode({"sub": "alice"}, "secret", ttl_seconds=60)
    with pytest.raises(tokens.TokenError):
        tokens.decode(token, "other-secret")


def test_tampered_token_fails():
    token = tokens.encode({"sub": "alice"}, "secret", ttl_seconds=60)
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}x.{signature}"
    with pytest.raises(tokens.TokenError):
        tokens.decode(tampered, "secret")


def test_expired_token_fails():
    token = tokens.encode({"sub": "alice"}, "secret", ttl_seconds=-1)
    with pytest.raises(tokens.TokenError):
        tokens.decode(token, "secret")


def test_malformed_token_fails():
    with pytest.raises(tokens.TokenError):
        tokens.decode("not.a.jwt.really", "secret")
