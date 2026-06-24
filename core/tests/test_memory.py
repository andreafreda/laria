"""Memory wrapper tests — FakeBackend only (no network, no mem0)."""
from __future__ import annotations

import os

from laria.config import reload_settings
from laria.memory import Scope, get_memory_backend
from laria.memory.fake import FakeBackend


def test_registry_defaults_to_fake():
    os.environ.pop("MEMORY_BACKEND", None)
    reload_settings()
    assert isinstance(get_memory_backend(), FakeBackend)


def test_write_and_recall():
    be = FakeBackend()
    scope = Scope(household="home")
    be.write(scope, "the cat is named Luna")
    be.write(scope, "favorite pizza is margherita")

    hits = be.recall(scope, "what is the cat name", k=5)
    assert hits
    assert "Luna" in hits[0].text


def test_crud_roundtrip():
    be = FakeBackend()
    scope = Scope(household="home")
    item = be.write(scope, "wifi password rotates monthly")

    assert be.get(scope, item.id) is not None
    be.update(scope, item.id, text="wifi password rotates weekly")
    assert "weekly" in be.get(scope, item.id).text
    assert be.delete(scope, item.id) is True
    assert be.get(scope, item.id) is None


def test_scope_isolation():
    be = FakeBackend()
    shared = Scope(household="home")
    alice = Scope(household="home", user_id="alice")
    bob = Scope(household="home", user_id="bob")

    be.write(shared, "front door code is 1234")
    be.write(alice, "alice secret diary entry")

    # bob sees shared but not alice's private item
    bob_hits = {i.text for i in be.recall(bob, "diary code", k=10)}
    assert "front door code is 1234" in bob_hits
    assert "alice secret diary entry" not in bob_hits

    # alice sees her own + shared
    alice_hits = {i.text for i in be.recall(alice, "diary code", k=10)}
    assert "alice secret diary entry" in alice_hits


def test_forget_scope():
    be = FakeBackend()
    scope = Scope(household="home")
    be.write(scope, "fact one")
    be.write(scope, "fact two")
    removed = be.forget(scope)
    assert removed == 2
    assert be.recall(scope, "fact", k=10) == []
