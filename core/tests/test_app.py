"""Composition-root tests: build_engine wires the right pieces (no network)."""
from __future__ import annotations

import os

import pytest

from laria.app import build_engine
from laria.config import reload_settings
from laria.engine import Engine


@pytest.fixture
def ollama_env():
    """Use the local-provider path so no API key is required to build the engine."""
    os.environ["LLM_PROVIDER"] = "ollama"
    reload_settings()
    yield
    os.environ.pop("LLM_PROVIDER", None)
    os.environ.pop("HA_ENABLED", None)
    reload_settings()


def test_build_engine_registers_domain_tools(ollama_env):
    engine = build_engine()
    assert isinstance(engine, Engine)
    names = {s["name"] for s in engine.registry.schemas()}
    # core tools plus every domain module
    assert {"get_memory", "recall"} <= names
    assert {"add_transaction", "get_balances"} <= names      # finance
    assert {"log_meal", "get_shopping_list"} <= names         # food
    assert {"record_bill", "get_bill_year"} <= names          # utilities


def test_ha_tools_off_by_default(ollama_env):
    names = {s["name"] for s in build_engine().registry.schemas()}
    assert "get_house_state" not in names


def test_ha_tools_on_when_enabled(ollama_env):
    os.environ["HA_ENABLED"] = "true"
    reload_settings()
    names = {s["name"] for s in build_engine().registry.schemas()}
    assert {"get_house_state", "control_device", "speak_alexa"} <= names
