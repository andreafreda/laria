"""HTTP JSON API for talking to the engine.

A small aiohttp app: a health check and a chat endpoint. It is deliberately a
clean JSON API (no server-rendered pages) so the native web UI, mobile clients
or other integrations all consume the same surface. The engine is injected with
``create_app`` so tests can pass a stub instead of a live LLM.
"""
from __future__ import annotations

import json
import logging

from aiohttp import web

from ..ingest import bank_statements
from ..storage import finance

logger = logging.getLogger(__name__)

# Typed key for stashing the engine on the app (aiohttp's recommended pattern).
ENGINE = web.AppKey("engine", object)


async def _health(request: web.Request) -> web.Response:
    """Liveness probe for load balancers and ``docker healthcheck``."""
    return web.json_response({"status": "ok"})


async def _chat(request: web.Request) -> web.Response:
    """Run one chat turn. Body: {user_id?, text, user_config?}. Returns {reply}.

    ``user_id`` defaults to "default" for single-user setups. A missing or empty
    ``text`` is a client error (400); an engine failure is reported as 500 with
    the detail logged, not leaked to the caller.
    """
    try:
        data = await request.json()
    except (json.JSONDecodeError, ValueError):
        return web.json_response({"error": "invalid JSON body"}, status=400)

    text = (data.get("text") or "").strip()
    if not text:
        return web.json_response({"error": "field 'text' is required"}, status=400)
    user_id = (data.get("user_id") or "default").strip()
    user_config = data.get("user_config") or {}

    engine = request.app[ENGINE]
    try:
        reply = await engine.chat(user_id, text, user_config)
    except Exception:
        logger.exception("chat failed for user %s", user_id)
        return web.json_response({"error": "internal error"}, status=500)
    return web.json_response({"reply": reply})


async def _import_statement(request: web.Request) -> web.Response:
    """Import a bank-statement file into an account.

    Multipart form: ``account`` (an existing account name) and ``file`` (a
    BancoPosta or Postepay csv/xlsx export). Parses the file, then bulk-imports
    the movements with dedup. Returns the parse and import counts. Client errors
    (missing fields, unknown account, unreadable format) are 400.
    """
    if not request.content_type.startswith("multipart/"):
        return web.json_response(
            {"error": "send a multipart form with 'account' and 'file'"}, status=400)

    account, content, filename = await _read_import_form(request)
    if not account or content is None:
        return web.json_response(
            {"error": "fields 'account' and 'file' are required"}, status=400)

    try:
        rows = bank_statements.rows_from_file(content, filename)
    except ImportError:
        return web.json_response(
            {"error": "xlsx files need the optional 'openpyxl' package; use csv"},
            status=400)

    parsed = bank_statements.parse(rows)
    if parsed.get("error"):
        return web.json_response({"error": parsed["error"]}, status=400)

    try:
        result = await finance.import_transactions(account, parsed["movements"])
    except ValueError as error:  # unknown account
        return web.json_response({"error": str(error)}, status=400)

    return web.json_response({**result, "format": parsed["format"],
                              "skipped": parsed["skipped"]})


async def _read_import_form(request: web.Request) -> tuple[str, bytes | None, str]:
    """Pull the account name and uploaded file out of the multipart request."""
    account = ""
    content: bytes | None = None
    filename = ""
    reader = await request.multipart()
    async for part in reader:
        if part.name == "account":
            account = (await part.text()).strip()
        elif part.name == "file":
            filename = part.filename or ""
            content = await part.read(decode=False)
    return account, content, filename


def create_app(engine) -> web.Application:
    """Build the aiohttp application around an engine.

    The engine is any object with ``async chat(user_id, text, user_config)``, so
    tests can inject a stub. Production wires the real one via ``build_engine``.
    """
    app = web.Application()
    app[ENGINE] = engine
    app.router.add_get("/health", _health)
    app.router.add_post("/api/chat", _chat)
    app.router.add_post("/api/finance/import", _import_statement)
    return app
