"""HaClient tests: the climate turn_off/on -> set_hvac_mode fallback."""
from __future__ import annotations

import aiohttp
import pytest

from laria.connectors.ha.client import HaClient, _climate_hvac_fallback


def test_fallback_only_for_climate_turn_service():
    assert _climate_hvac_fallback("climate", "turn_off", 400) == "off"
    assert _climate_hvac_fallback("climate", "turn_on", 500) == "auto"
    assert _climate_hvac_fallback("climate", "set_temperature", 400) is None
    assert _climate_hvac_fallback("light", "turn_off", 400) is None
    assert _climate_hvac_fallback("climate", "turn_off", 404) is None


async def test_call_service_retries_with_set_hvac_mode(monkeypatch):
    client = HaClient(url="http://ha.local", token="t")
    calls: list = []

    async def fake_post(path, data):
        calls.append((path, data))
        if len(calls) == 1:
            raise aiohttp.ClientResponseError(None, (), status=400)
        return {"ok": True}

    monkeypatch.setattr(client, "_post", fake_post)
    result = await client.call_service("climate", "turn_off", {"entity_id": "climate.ac"})

    assert result == {"ok": True}
    assert calls[0][0].endswith("/climate/turn_off")
    assert calls[1][0].endswith("/climate/set_hvac_mode")
    assert calls[1][1] == {"entity_id": "climate.ac", "hvac_mode": "off"}


async def test_call_service_reraises_unrelated_error(monkeypatch):
    client = HaClient(url="http://ha.local", token="t")

    async def fake_post(path, data):
        raise aiohttp.ClientResponseError(None, (), status=400)

    monkeypatch.setattr(client, "_post", fake_post)
    with pytest.raises(aiohttp.ClientResponseError):
        await client.call_service("light", "turn_off", {"entity_id": "light.k"})
