"""Proactive food broadcasts sent on a fixed daily/weekly schedule.

Three jobs, ported from HARIA: the day's meal plan each morning, a pantry
expiry alert, and a weekly per-member calorie report. They are broadcasts, not
per-user records, so the scheduler runs them on a built-in cron and this class
sends the result to every user who has a linked Telegram chat.

The weekly report is per member: it compares a member's average logged calories
against their profile target, so it is sent only to users whose login is linked
to a profile.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

from ..storage import food, identity

if TYPE_CHECKING:
    from .telegram import TelegramClient

logger = logging.getLogger(__name__)

# Order meals as they fall through the day, regardless of insertion order.
_MEAL_ORDER = {"breakfast": 0, "lunch": 1, "snack": 2, "dinner": 3}


class FoodBroadcaster:
    """Builds and sends the scheduled food messages over Telegram."""

    def __init__(self, client: "TelegramClient"):
        self._client = client

    async def daily_plan(self) -> None:
        """Send today's meal plan to everyone with a linked chat."""
        today = date.today().isoformat()
        plan = await food.get_meal_plan(today, today)
        if not plan:
            return
        plan.sort(key=lambda m: (_MEAL_ORDER.get(m["meal_type"], 9), m.get("member") or ""))
        lines = ["🍽️ Today's meals:"]
        for meal in plan:
            who = (meal.get("member") or "").strip()
            prefix = f"{who.capitalize()} - " if who else ""
            line = f"- {meal['meal_type'].capitalize()}: {prefix}{meal['items']}"
            if meal.get("recipe"):
                line += f" ({meal['recipe']})"
            lines.append(line)
        await self._broadcast("\n".join(lines))

    async def pantry_alert(self) -> None:
        """Warn everyone about pantry items expiring within three days."""
        expiring = await food.get_pantry_expiring(3)
        if not expiring:
            return
        lines = ["⚠️ Expiring soon in the pantry:"]
        for item in expiring:
            text = f"- {item['name']}"
            if item.get("qty"):
                text += f" {item['qty']}"
            if item.get("expires_on"):
                text += f" (by {item['expires_on']})"
            lines.append(text)
        await self._broadcast("\n".join(lines))

    async def weekly_report(self) -> None:
        """Send each linked member their average calories over the last 7 days."""
        end = date.today()
        days = [(end - timedelta(days=offset)).isoformat() for offset in range(7)]
        profile_names = {p["id"]: p["name"] for p in await identity.list_profiles()}
        for user in await identity.list_users():
            chat_id = user.get("telegram_chat_id")
            member = profile_names.get(user.get("profile_id"))
            if not chat_id or not member:
                continue
            message = await self._member_report(member)
            if message:
                await self._send(chat_id, message)

    async def _member_report(self, member: str) -> str | None:
        """Build one member's weekly report, or None when nothing was logged."""
        end = date.today()
        totals = [await food.get_day_totals(member, (end - timedelta(days=offset)).isoformat())
                  for offset in range(7)]
        logged = [t for t in totals if t["meals"] > 0]
        if not logged:
            return None
        average = round(sum(t["kcal"] for t in logged) / len(logged))
        message = (f"📊 Weekly report for {member.capitalize()}:\n"
                   f"Average {average} kcal/day over {len(logged)} tracked days.")
        profile = await food.get_profile(member)
        target = profile.get("kcal_target") if profile else None
        if target:
            delta = average - target
            direction = "above" if delta > 0 else "below"
            message += f"\nTarget {target} kcal: {abs(delta)} kcal {direction} on average."
        return message

    async def _broadcast(self, text: str) -> None:
        """Send the same text to every user with a linked Telegram chat."""
        for user in await identity.list_users():
            chat_id = user.get("telegram_chat_id")
            if chat_id:
                await self._send(chat_id, text)

    async def _send(self, chat_id: str, text: str) -> None:
        try:
            await self._client.send_message(int(chat_id), text)
        except Exception as error:
            logger.warning("food broadcast to %s failed: %s", chat_id, error)
