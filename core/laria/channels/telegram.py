"""Telegram channel: talk to the engine from a Telegram chat.

A thin bridge over the Telegram Bot API (plain HTTP via aiohttp, no extra
dependency). Each incoming text message becomes one engine turn, keyed by the
chat id, and the reply is sent back. The message-handling logic is separated from
the polling and HTTP so it can be tested with stubs.
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from ..app import build_engine
from ..config import get_settings
from ..engine import Engine
from ..storage import identity, init_db

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
        await client.send_message(chat_id, "This chat is not linked to a LARIA account.")
        return False

    reply = await engine.chat(str(user["id"]), text, {})
    await client.send_message(chat_id, reply)
    return True


async def run(engine: Engine, token: str) -> None:
    """Poll Telegram forever, handling each update. Advances the offset so each
    update is processed once."""
    offset = 0
    async with aiohttp.ClientSession() as session:
        client = TelegramClient(token, session)
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
                except Exception:
                    logger.exception("failed to handle update %s", update.get("update_id"))


def serve() -> None:
    """Entry point: build the engine and run the Telegram poller."""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    if not settings.telegram_token:
        raise SystemExit("TELEGRAM_TOKEN is not set")

    async def _main() -> None:
        await init_db()
        await run(build_engine(settings), settings.telegram_token)

    asyncio.run(_main())


if __name__ == "__main__":
    serve()
