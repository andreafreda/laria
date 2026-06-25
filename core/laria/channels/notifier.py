"""Proactive delivery for scheduled jobs over Telegram.

The scheduler fires reminders and briefings but does not know how to reach the
user. This notifier closes that gap: it resolves the stored user id to a linked
Telegram chat and sends the message. It is the pair of callbacks the scheduler
calls, kept separate so the scheduler stays delivery-agnostic and testable.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..llm import LLMProvider
from ..modules import news
from ..storage import identity, misc

if TYPE_CHECKING:
    from .telegram import TelegramClient

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Delivers due reminders and news briefings to the linked Telegram chat.

    Construct it with the Telegram client and the LLM provider (the provider is
    needed only to summarize briefings). Pass ``fire_reminder`` and
    ``fire_briefing`` to the scheduler as its callbacks.
    """

    def __init__(self, client: TelegramClient, provider: LLMProvider):
        self._client = client
        self._provider = provider

    async def fire_reminder(self, reminder: dict) -> None:
        """Send a due reminder, then retire it if it was one-shot.

        A one-shot reminder is deactivated only after a successful send, so a
        delivery failure leaves it active to retry on the next scheduler start. A
        recurring reminder always stays active.
        """
        chat_id = await self._resolve_chat_id(reminder["user_id"])
        if chat_id is None:
            logger.warning("reminder %s has no linked Telegram chat", reminder.get("id"))
            return
        try:
            await self._client.send_message(int(chat_id), f"⏰ Reminder: {reminder['message']}")
        except Exception as error:
            logger.error("failed to send reminder %s: %s", reminder.get("id"), error)
            return
        if not reminder.get("recurring"):
            await misc.deactivate_reminder(reminder["id"])

    async def fire_briefing(self, briefing: dict) -> None:
        """Generate a briefing's summary and send it to the linked chat."""
        chat_id = await self._resolve_chat_id(briefing["user_id"])
        if chat_id is None:
            logger.warning("briefing %s has no linked Telegram chat", briefing.get("id"))
            return
        try:
            text = await news.generate(
                self._provider, briefing["topics"], briefing["user_id"],
                briefing.get("num_news", 5))
            await self._client.send_message(int(chat_id), text)
        except Exception as error:
            logger.error("failed to send briefing %s: %s", briefing.get("id"), error)

    async def _resolve_chat_id(self, user_id: str) -> str | None:
        """Map a stored user id to its linked Telegram chat id, or None.

        Reminders and briefings are stored under the LARIA user id; delivery
        needs the chat id recorded on that user's account.
        """
        if not user_id or not str(user_id).isdigit():
            return None
        user = await identity.get_user_by_id(int(user_id))
        return user["telegram_chat_id"] if user else None
