"""Telegram channel: talk to the engine from a Telegram chat.

A thin bridge over the Telegram Bot API (plain HTTP via aiohttp, no extra
dependency). Each incoming text message becomes one engine turn, keyed by the
chat id, and the reply is sent back. The message-handling logic is separated from
the polling and HTTP so it can be tested with stubs.
"""
from __future__ import annotations

import asyncio
import logging
import secrets

import aiohttp

from .. import auth
from ..app import build_engine
from ..config import get_settings
from ..engine import Engine
from ..errors import report_error
from ..llm import get_provider
from ..scheduler import Scheduler
from ..storage import identity, init_db, misc
from .food_jobs import FoodBroadcaster
from .notifier import TelegramNotifier

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
_POLL_TIMEOUT = 30  # long-poll seconds; Telegram holds the request open


class TelegramClient:
    """Minimal Telegram Bot API client: receive updates and send messages."""

    def __init__(self, token: str, session: aiohttp.ClientSession):
        self._token = token
        self._session = session

    async def get_updates(self, offset: int) -> list[dict]:
        """Long-poll for new updates starting at ``offset`` (returns [] on timeout)."""
        url = _API.format(token=self._token, method="getUpdates")
        params = {"offset": offset, "timeout": _POLL_TIMEOUT}
        async with self._session.get(
            url, params=params,
            timeout=aiohttp.ClientTimeout(total=_POLL_TIMEOUT + 10)) as resp:
            data = await resp.json()
        return data.get("result", [])

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a text message to a chat."""
        url = _API.format(token=self._token, method="sendMessage")
        async with self._session.post(url, json={"chat_id": chat_id, "text": text}) as resp:
            resp.raise_for_status()


async def handle_update(update: dict, engine: Engine, client: TelegramClient) -> bool:
    """Process one update: run a text message through the engine and reply.

    Only chats linked to a LARIA user (allowlist via ``telegram_chat_id``) are
    served; an unlinked chat gets a short refusal so the bot is not an open door.
    The engine runs under the linked user's id, so a Telegram conversation shares
    identity and memory with that user's web login.

    Returns True if a message was handled, False for ignored updates (no message,
    a non-text message, or an unlinked chat).
    """
    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not text or chat_id is None:
        return False

    user = await identity.get_user_by_telegram(str(chat_id))
    if user is None:
        if await _try_claim(text, chat_id, client):
            return True
        await client.send_message(chat_id, "This chat is not linked to a LARIA account.")
        return False

    if text.startswith("/"):
        return await _handle_command(text, user, client, chat_id)

    reply = await engine.chat(str(user["id"]), text, {})
    await client.send_message(chat_id, reply)
    return True


async def _try_claim(text: str, chat_id: int, client: TelegramClient) -> bool:
    """Link an unlinked chat to the owner via a one-time claim code.

    A first-run bootstrap so the bot is usable without the web UI: the admin
    sets LARIA_TELEGRAM_CLAIM_CODE, then sends "/claim <code>" (or
    "/start <code>") from the chat that should become the owner's. Returns True
    when the message was a claim attempt (handled with a reply), False otherwise
    so normal refusal applies. Claiming is refused once the owner already has a
    linked chat.
    """
    settings = get_settings()
    code = settings.telegram_claim_code
    if not code:
        return False
    parts = text.split()
    if parts[0] not in ("/claim", "/start") or len(parts) < 2 or parts[1] != code:
        return False

    owner = await identity.get_user_by_username(settings.auth.admin_user)
    if owner is None:
        return False
    if owner.get("telegram_chat_id"):
        await client.send_message(chat_id, "LARIA is already linked to another chat.")
        return True
    await identity.link_telegram(owner["id"], str(chat_id))
    await client.send_message(
        chat_id, "This chat is now linked to LARIA. Ask me anything, for example: what can you do?")
    return True


async def _handle_command(text: str, user: dict, client: TelegramClient,
                          chat_id: int) -> bool:
    """Handle a bot command from a linked user. Returns True if recognized.

    ``/reset`` is a recovery path that works without email: because the chat is
    already verified (allowlist), it sets a temporary password and forces a
    change at the next web login.
    """
    command = text.split()[0]
    if command == "/reset":
        temporary = secrets.token_urlsafe(9)
        await auth.reset_password(user["id"], temporary, must_change=True)
        await client.send_message(
            chat_id,
            f"Temporary password: {temporary}\n"
            "Log in on the web; you will be asked to set a new one.")
        return True
    await client.send_message(chat_id, "Unknown command. Try /reset.")
    return True


async def run(engine: Engine, client: TelegramClient) -> None:
    """Poll Telegram forever, handling each update. Advances the offset so each
    update is processed once. The caller owns the client's HTTP session, so the
    same client can also be used for proactive sends."""
    offset = 0
    logger.info("Telegram channel started")
    while True:
        try:
            updates = await client.get_updates(offset)
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            logger.warning("Telegram poll failed, retrying: %s", error)
            await asyncio.sleep(3)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            try:
                await handle_update(update, engine, client)
            except Exception as error:
                update_id = update.get("update_id")
                logger.exception("failed to handle update %s", update_id)
                await report_error("telegram", f"failed to handle update {update_id}", error)


async def _load_scheduled_jobs(scheduler: Scheduler) -> None:
    """Queue every active reminder and briefing so they fire after a restart."""
    for reminder in await misc.get_active_reminders():
        scheduler.schedule_reminder(reminder)
    for briefing in await misc.get_active_briefings():
        scheduler.schedule_briefing(briefing)


def _schedule_food_jobs(scheduler: Scheduler, food_jobs: FoodBroadcaster) -> None:
    """Register the built-in proactive food broadcasts on their daily/weekly cron."""
    scheduler.schedule_cron("food_daily_plan", "0 8 * * *", food_jobs.daily_plan)
    scheduler.schedule_cron("food_pantry_alert", "30 8 * * *", food_jobs.pantry_alert)
    scheduler.schedule_cron("food_weekly_report", "0 20 * * 0", food_jobs.weekly_report)


def _schedule_mqtt_mirror(scheduler: Scheduler, settings) -> None:
    """Mirror LARIA data to MQTT every 15 minutes, when a broker is set.

    Two jobs: LARIA's own namespaced finance sensors, and the HARIA compatible
    dashboard entities (bollette/economia/food). Only registered if a HA MQTT
    host is configured, so a deployment without MQTT runs unchanged. Each publish
    is best effort: a broker outage logs and is retried at the next tick.
    """
    if not settings.ha.mqtt_host:
        return
    from ..connectors.ha import (
        MqttMirror, publish_dashboards, publish_finance, publish_native)
    mirror = MqttMirror(settings.ha)

    async def _refresh() -> None:
        try:
            await publish_finance(mirror)
        except Exception as error:
            logger.warning("MQTT finance mirror failed: %s", error)

    async def _refresh_native() -> None:
        try:
            await publish_native(mirror)
        except Exception as error:
            logger.warning("MQTT native dashboard publish failed: %s", error)

    async def _refresh_compat() -> None:
        try:
            await publish_dashboards(mirror)
        except Exception as error:
            logger.warning("MQTT compat dashboard publish failed: %s", error)

    scheduler.schedule_cron("mqtt_finance_mirror", "*/15 * * * *", _refresh)
    # Canonical LARIA-native dashboard entities (laria_ namespace, English model).
    scheduler.schedule_cron("mqtt_dashboards_native", "*/15 * * * *", _refresh_native)
    # HARIA-compat entities, kept only until the Lovelace dashboards point at the
    # native ones; removed on the HARIA cut-over.
    scheduler.schedule_cron("mqtt_dashboards", "*/15 * * * *", _refresh_compat)


def serve() -> None:
    """Entry point: run the Telegram bot with proactive scheduling.

    Builds the engine wired to a scheduler so reminders and briefings created in
    chat fire live, reloads any jobs saved from previous runs, then polls for
    messages. The Telegram client's HTTP session is shared between the poller and
    the proactive notifier.
    """
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    if not settings.telegram_token:
        raise SystemExit("TELEGRAM_TOKEN is not set")

    async def _main() -> None:
        await init_db()
        await auth.ensure_owner()  # seed the owner so a chat can claim it
        async with aiohttp.ClientSession() as session:
            client = TelegramClient(settings.telegram_token, session)
            notifier = TelegramNotifier(client, get_provider(settings))
            scheduler = Scheduler(notifier.fire_reminder, notifier.fire_briefing)
            engine = build_engine(settings, scheduler=scheduler)
            scheduler.start()
            await _load_scheduled_jobs(scheduler)
            _schedule_food_jobs(scheduler, FoodBroadcaster(client))
            scheduler.schedule_cron("events_daily", "0 8 * * *", notifier.send_due_events)
            _schedule_mqtt_mirror(scheduler, settings)
            await run(engine, client)

    asyncio.run(_main())


if __name__ == "__main__":
    serve()
