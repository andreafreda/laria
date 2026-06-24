"""Home Assistant client over the official REST and WebSocket APIs.

Talks to any reachable Home Assistant with a long-lived token, not through the
Supervisor, so LARIA can drive an HA instance from outside the box it runs on.
The url and token are injected (see ``from_settings``) to keep the client easy
to construct in tests and free of global state.

Failures are mapped to plain Python errors (ConnectionError, PermissionError,
TimeoutError) so callers can react without knowing aiohttp.
"""
from __future__ import annotations

import aiohttp

from ...config import HASettings, get_settings

_TIMEOUT = aiohttp.ClientTimeout(total=10)


class HaClient:
    def __init__(self, url: str, token: str):
        self._url = url.rstrip("/")
        self._token = token

    @classmethod
    def from_settings(cls, settings: HASettings | None = None) -> "HaClient":
        """Build a client from the HA section of the app settings."""
        ha = settings or get_settings().ha
        return cls(url=ha.url, token=ha.token)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def get_states(self, entity_ids: list[str] | None = None) -> list[dict]:
        """Live entity states, optionally narrowed to specific entity_ids.

        Returns a slim shape per entity (entity_id, state, attributes). Omitting
        ``entity_ids`` returns every entity, which is large; prefer naming the
        ones you need.
        """
        states = await self._get("/api/states")
        if entity_ids:
            states = [s for s in states if s["entity_id"] in entity_ids]
        return [
            {"entity_id": s["entity_id"], "state": s["state"],
             "attributes": s.get("attributes", {})}
            for s in states
        ]

    async def call_service(self, domain: str, service: str, data: dict,
                           return_response: bool = False) -> dict:
        """Call an HA service (e.g. light.turn_on) and return its JSON response."""
        path = f"/api/services/{domain}/{service}"
        if return_response:
            path += "?return_response"
        return await self._post(path, data)

    async def get_calendar_events(self, entity_id: str,
                                  start_iso: str, end_iso: str) -> list[dict]:
        """Events of a calendar via REST (includes the uid, unlike the service)."""
        data = await self._get(
            f"/api/calendars/{entity_id}?start={start_iso}&end={end_iso}")
        return data if isinstance(data, list) else []

    async def ws_command(self, payload: dict) -> dict:
        """Run a WebSocket command for APIs that REST does not expose.

        Used for things like calendar event create/update/delete. Authenticates
        with the token, sends the command as message id 1, and returns its
        ``result`` (raising on an error result).
        """
        ws_url = (self._url.replace("https://", "wss://").replace("http://", "ws://")
                  + "/api/websocket")
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.ws_connect(ws_url) as ws:
                    await ws.receive_json()  # auth_required
                    await ws.send_json({"type": "auth", "access_token": self._token})
                    ack = await ws.receive_json()
                    if ack.get("type") != "auth_ok":
                        raise PermissionError("HA WebSocket auth failed")
                    await ws.send_json({"id": 1, **payload})
                    return await self._await_ws_result(ws)
        except aiohttp.ClientConnectorError:
            raise ConnectionError(f"Home Assistant unreachable at {self._url}")

    async def _await_ws_result(self, ws: aiohttp.ClientWebSocketResponse) -> dict:
        """Read messages until the result for command id 1 arrives."""
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "result" and msg.get("id") == 1:
                if not msg.get("success"):
                    detail = (msg.get("error") or {}).get("message", "WebSocket error")
                    raise RuntimeError(f"Home Assistant: {detail}")
                return msg.get("result") or {}

    async def _get(self, path: str):
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.get(self._url + path, headers=self._headers()) as resp:
                    return await self._read(resp)
        except aiohttp.ClientConnectorError:
            raise ConnectionError(f"Home Assistant unreachable at {self._url}")

    async def _post(self, path: str, data: dict):
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.post(self._url + path, headers=self._headers(),
                                        json=data) as resp:
                    return await self._read(resp)
        except aiohttp.ClientConnectorError:
            raise ConnectionError(f"Home Assistant unreachable at {self._url}")

    async def _read(self, resp: aiohttp.ClientResponse):
        """Turn an HA response into JSON, mapping auth failures to PermissionError."""
        if resp.status == 401:
            raise PermissionError("Home Assistant token invalid or expired")
        resp.raise_for_status()
        return await resp.json()
