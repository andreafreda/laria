"""HTTP JSON API for talking to the engine.

A small aiohttp app: a health check and a chat endpoint. It is deliberately a
clean JSON API (no server-rendered pages) so the native web UI, mobile clients
or other integrations all consume the same surface. The engine is injected with
``create_app`` so tests can pass a stub instead of a live LLM.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date

from aiohttp import web

from .. import auth
from ..ingest import bank_statements
from ..storage import finance, identity

logger = logging.getLogger(__name__)

# Typed key for stashing the engine on the app (aiohttp's recommended pattern).
ENGINE = web.AppKey("engine", object)
# Request key holding the authenticated user's token claims.
_USER = "user"
# Routes the middleware lets through without a Bearer token. The WebSocket chat
# authenticates itself from a query-string token, since browsers cannot set
# headers on a WebSocket handshake.
_PUBLIC_PATHS = frozenset({"/health", "/api/auth/login", "/api/chat/ws"})


@web.middleware
async def _auth_middleware(request: web.Request, handler):
    """Require a valid Bearer token on every route except the public ones.

    On success the token claims are stashed on the request for handlers to read;
    on a missing or invalid token the request is rejected with 401 before it
    reaches the handler.
    """
    # Only API routes (other than the public ones) need a token; static UI files
    # and the SPA fallback are served freely.
    needs_auth = request.path.startswith("/api/") and request.path not in _PUBLIC_PATHS
    if not needs_auth:
        return await handler(request)

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return web.json_response({"error": "authentication required"}, status=401)
    try:
        request[_USER] = auth.verify_token(header[len("Bearer "):])
    except auth.AuthError:
        return web.json_response({"error": "invalid or expired token"}, status=401)
    return await handler(request)


async def _health(request: web.Request) -> web.Response:
    """Liveness probe for load balancers and ``docker healthcheck``."""
    return web.json_response({"status": "ok"})


async def _login(request: web.Request) -> web.Response:
    """Exchange username and password for a login token. Bad credentials are 401.

    Returns {token, must_change}; ``must_change`` is true after a temporary
    password, signalling the client to force a password change.
    """
    try:
        data = await request.json()
    except (json.JSONDecodeError, ValueError):
        return web.json_response({"error": "invalid JSON body"}, status=400)
    try:
        token = await auth.authenticate(data.get("username", ""), data.get("password", ""))
    except auth.AuthError:
        return web.json_response({"error": "invalid username or password"}, status=401)
    must_change = auth.verify_token(token).get("must_change", False)
    return web.json_response({"token": token, "must_change": must_change})


async def _change_password(request: web.Request) -> web.Response:
    """Change the authenticated user's password (also clears the must-change flag)."""
    try:
        data = await request.json()
    except (json.JSONDecodeError, ValueError):
        return web.json_response({"error": "invalid JSON body"}, status=400)
    new_password = data.get("new_password") or ""
    if len(new_password) < 8:
        return web.json_response(
            {"error": "new_password must be at least 8 characters"}, status=400)
    await auth.change_password(request[_USER]["sub"], new_password)
    return web.json_response({"ok": True})


async def _chat(request: web.Request) -> web.Response:
    """Run one chat turn. Body: {text, user_config?}. Returns {reply}.

    The user identity comes from the auth token, not the body, so a client can
    only ever talk as itself. A missing or empty ``text`` is a client error
    (400); an engine failure is reported as 500 with the detail logged, not
    leaked to the caller.
    """
    try:
        data = await request.json()
    except (json.JSONDecodeError, ValueError):
        return web.json_response({"error": "invalid JSON body"}, status=400)

    text = (data.get("text") or "").strip()
    if not text:
        return web.json_response({"error": "field 'text' is required"}, status=400)
    user_id = str(request[_USER]["sub"])
    user_config = data.get("user_config") or {}

    engine = request.app[ENGINE]
    try:
        reply = await engine.chat(user_id, text, user_config)
    except Exception:
        logger.exception("chat failed for user %s", user_id)
        return web.json_response({"error": "internal error"}, status=500)
    return web.json_response({"reply": reply})


async def _chat_ws(request: web.Request) -> web.WebSocketResponse | web.Response:
    """Chat over a persistent WebSocket: send {text}, receive {reply}.

    Authenticates from a ``?token=`` query parameter (a WebSocket handshake
    cannot carry an Authorization header). Each text frame is one engine turn
    under the token's user; replies and errors are sent back as JSON frames.
    This is request/reply over a kept-open socket; token-by-token streaming is a
    later addition that needs provider streaming support.
    """
    try:
        claims = auth.verify_token(request.query.get("token", ""))
    except auth.AuthError:
        return web.json_response({"error": "authentication required"}, status=401)

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    engine = request.app[ENGINE]
    user_id = str(claims["sub"])

    async for frame in ws:
        if frame.type is not web.WSMsgType.TEXT:
            continue
        try:
            text = (json.loads(frame.data).get("text") or "").strip()
        except (json.JSONDecodeError, ValueError, AttributeError):
            await ws.send_json({"error": "invalid message"})
            continue
        if not text:
            await ws.send_json({"error": "field 'text' is required"})
            continue
        try:
            reply = await engine.chat(user_id, text, {})
        except Exception:
            logger.exception("ws chat failed for user %s", user_id)
            await ws.send_json({"error": "internal error"})
            continue
        await ws.send_json({"reply": reply})
    return ws


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


# --------------------------------------------------------------------------- #
# Finance read models (for the dashboards)
# --------------------------------------------------------------------------- #

async def _finance_balances(request: web.Request) -> web.Response:
    """Current balance of every active account."""
    return web.json_response(await finance.get_balances())


async def _finance_summary(request: web.Request) -> web.Response:
    """Income/expenses/net + per-category breakdown. Query: date_from, date_to."""
    return web.json_response(await finance.expense_summary(
        date_from=request.query.get("date_from"),
        date_to=request.query.get("date_to")))


async def _finance_matrix(request: web.Request) -> web.Response:
    """Category x month spending matrix. Query: months (optional, default all)."""
    months = request.query.get("months")
    return web.json_response(await finance.monthly_category_matrix(
        int(months) if months else None))


async def _finance_budget_status(request: web.Request) -> web.Response:
    """Budget tracking for a month. Query: year, month (default current)."""
    today = date.today()
    return web.json_response(await finance.get_budget_status(
        int(request.query.get("year", today.year)),
        int(request.query.get("month", today.month))))


async def _finance_goals(request: web.Request) -> web.Response:
    """Savings goals with progress."""
    return web.json_response(await finance.get_goals())


# --------------------------------------------------------------------------- #
# Admin (owner only): manage profiles, users, guardianships
# --------------------------------------------------------------------------- #

def _require_owner(request: web.Request) -> web.Response | None:
    """Return a 403 response unless the caller is the owner, else None to proceed."""
    if request[_USER].get("role") != "owner":
        return web.json_response({"error": "owner role required"}, status=403)
    return None


def _public_user(user: dict) -> dict:
    """A user dict safe to return over the API (without the password hash)."""
    return {k: v for k, v in user.items() if k != "password_hash"}


async def _admin_list_users(request: web.Request) -> web.Response:
    """List all logins (without password hashes). Owner only."""
    if denied := _require_owner(request):
        return denied
    return web.json_response([_public_user(u) for u in await identity.list_users()])


async def _admin_list_profiles(request: web.Request) -> web.Response:
    """List all household profiles. Owner only."""
    if denied := _require_owner(request):
        return denied
    return web.json_response(await identity.list_profiles())


async def _admin_create_profile(request: web.Request) -> web.Response:
    """Create a household member profile. Body: {name, is_dependent?}. Owner only."""
    if denied := _require_owner(request):
        return denied
    data = await _json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return web.json_response({"error": "field 'name' is required"}, status=400)
    profile_id = await identity.create_profile(name, bool(data.get("is_dependent", False)))
    return web.json_response({"id": profile_id, "name": name})


async def _admin_create_user(request: web.Request) -> web.Response:
    """Create a login. Body: {username, password, role?, profile_id?}. Owner only."""
    if denied := _require_owner(request):
        return denied
    data = await _json(request)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or len(password) < 8:
        return web.json_response(
            {"error": "username and a password of at least 8 characters are required"},
            status=400)
    user_id = await auth.create_user_account(
        username, password, role=data.get("role", "adult"),
        profile_id=data.get("profile_id"))
    return web.json_response({"id": user_id, "username": username})


async def _admin_reset_password(request: web.Request) -> web.Response:
    """Reset a user's password. Body: {user_id, new_password, must_change?}. Owner only."""
    if denied := _require_owner(request):
        return denied
    data = await _json(request)
    new_password = data.get("new_password") or ""
    if not data.get("user_id") or len(new_password) < 8:
        return web.json_response(
            {"error": "user_id and a password of at least 8 characters are required"},
            status=400)
    await auth.reset_password(data["user_id"], new_password,
                              must_change=bool(data.get("must_change", True)))
    return web.json_response({"ok": True})


async def _admin_link_telegram(request: web.Request) -> web.Response:
    """Bind a Telegram chat to a user. Body: {user_id, chat_id}. Owner only."""
    if denied := _require_owner(request):
        return denied
    data = await _json(request)
    if not data.get("user_id") or not data.get("chat_id"):
        return web.json_response({"error": "user_id and chat_id are required"}, status=400)
    await identity.link_telegram(data["user_id"], str(data["chat_id"]))
    return web.json_response({"ok": True})


async def _admin_add_guardianship(request: web.Request) -> web.Response:
    """Let a user act for a profile. Body: {guardian_user_id, profile_id}. Owner only."""
    if denied := _require_owner(request):
        return denied
    data = await _json(request)
    if not data.get("guardian_user_id") or not data.get("profile_id"):
        return web.json_response(
            {"error": "guardian_user_id and profile_id are required"}, status=400)
    await identity.add_guardianship(data["guardian_user_id"], data["profile_id"])
    return web.json_response({"ok": True})


async def _json(request: web.Request) -> dict:
    """Parse a JSON body, returning {} on an empty or invalid one."""
    try:
        return await request.json()
    except (json.JSONDecodeError, ValueError):
        return {}


def create_app(engine) -> web.Application:
    """Build the aiohttp application around an engine.

    The engine is any object with ``async chat(user_id, text, user_config)``, so
    tests can inject a stub. Production wires the real one via ``build_engine``.
    """
    app = web.Application(middlewares=[_auth_middleware])
    app[ENGINE] = engine
    app.router.add_get("/health", _health)
    app.router.add_post("/api/auth/login", _login)
    app.router.add_post("/api/auth/change-password", _change_password)
    app.router.add_post("/api/chat", _chat)
    app.router.add_get("/api/chat/ws", _chat_ws)
    app.router.add_post("/api/finance/import", _import_statement)
    app.router.add_get("/api/finance/balances", _finance_balances)
    app.router.add_get("/api/finance/summary", _finance_summary)
    app.router.add_get("/api/finance/matrix", _finance_matrix)
    app.router.add_get("/api/finance/budget-status", _finance_budget_status)
    app.router.add_get("/api/finance/goals", _finance_goals)
    app.router.add_get("/api/admin/users", _admin_list_users)
    app.router.add_get("/api/admin/profiles", _admin_list_profiles)
    app.router.add_post("/api/admin/profiles", _admin_create_profile)
    app.router.add_post("/api/admin/users", _admin_create_user)
    app.router.add_post("/api/admin/users/reset-password", _admin_reset_password)
    app.router.add_post("/api/admin/users/link-telegram", _admin_link_telegram)
    app.router.add_post("/api/admin/guardianships", _admin_add_guardianship)
    _serve_ui(app)
    return app


def _serve_ui(app: web.Application) -> None:
    """Serve the built Angular UI when LARIA_UI_DIR points to its files.

    Registered after the API routes so they win. A catch-all returns the
    requested file if it exists, else index.html, which is what a single-page app
    needs so client-side routes (e.g. /dashboard) load. Unset in dev, where the
    UI is served separately by `ng serve`.
    """
    ui_dir = os.environ.get("LARIA_UI_DIR")
    if not ui_dir or not os.path.isdir(ui_dir):
        return
    index_file = os.path.join(ui_dir, "index.html")

    async def spa(request: web.Request) -> web.StreamResponse:
        requested = request.match_info.get("tail", "")
        candidate = os.path.normpath(os.path.join(ui_dir, requested))
        # Guard against path traversal outside the UI directory.
        if candidate.startswith(ui_dir) and os.path.isfile(candidate):
            return web.FileResponse(candidate)
        return web.FileResponse(index_file)

    app.router.add_get("/{tail:.*}", spa)
