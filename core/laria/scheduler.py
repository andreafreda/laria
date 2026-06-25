"""Job scheduler: fires reminders at their time and news briefings on a cron.

Wraps APScheduler's asyncio scheduler. The scheduler itself knows nothing about
Telegram or news: it is given two async callbacks at construction
(``on_reminder`` and ``on_briefing``) and calls them when a job is due. The
channel layer supplies callbacks that actually deliver the message, which keeps
delivery testable and the scheduler reusable.

Cron strings use standard 5-field crontab syntax with Unix day-of-week numbering
(0 and 7 are Sunday). APScheduler numbers the week differently, so we translate
the day-of-week field by name before building the trigger.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)

ReminderCallback = Callable[[dict], Awaitable[None]]
BriefingCallback = Callable[[dict], Awaitable[None]]

# Unix crontab: day-of-week 0-6 = Sun-Sat (0 or 7 = Sun). APScheduler numbers
# 0-6 = Mon-Sun, and from_crontab does not convert, so we map the Unix numbers to
# APScheduler's unambiguous names and build the trigger by hand.
_DAY_OF_WEEK_NAMES = {"0": "sun", "7": "sun", "1": "mon", "2": "tue", "3": "wed",
                      "4": "thu", "5": "fri", "6": "sat"}


def _convert_day_of_week(field: str) -> str:
    """Rewrite Unix day-of-week numbers to APScheduler names (keeps *, lists,
    ranges intact). A number after '/' is a step, so leave those alone."""
    if field == "*":
        return "*"
    return re.sub(r"(?<![/\d])\d+",
                  lambda m: _DAY_OF_WEEK_NAMES.get(m.group(0), m.group(0)), field)


def cron_trigger(expression: str) -> CronTrigger:
    """Build a CronTrigger from a standard 5-field crontab string.

    Day-of-week keeps Unix semantics (5 means Friday). Raises ValueError if the
    expression does not have exactly five fields.
    """
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError(f"cron must have 5 fields, got: {expression!r}")
    minute, hour, day_of_month, month, day_of_week = parts
    return CronTrigger(minute=minute, hour=hour, day=day_of_month, month=month,
                       day_of_week=_convert_day_of_week(day_of_week))


class Scheduler:
    """Schedules reminders (one-shot or recurring) and recurring news briefings.

    Construct it with the two delivery callbacks, call ``start`` once, then add
    jobs as they are created. The callbacks receive the stored reminder/briefing
    dict so they can decide how to deliver it.
    """

    def __init__(self, on_reminder: ReminderCallback, on_briefing: BriefingCallback):
        self._scheduler = AsyncIOScheduler()
        self._on_reminder = on_reminder
        self._on_briefing = on_briefing

    def start(self) -> None:
        """Start the underlying scheduler so queued jobs begin firing."""
        self._scheduler.start()

    def shutdown(self) -> None:
        """Stop the scheduler without waiting for running jobs to finish."""
        self._scheduler.shutdown(wait=False)

    def is_running(self) -> bool:
        """True once ``start`` has been called and not yet shut down."""
        return self._scheduler.running

    def schedule_reminder(self, reminder: dict) -> bool:
        """Queue one reminder. Returns False (and schedules nothing) when the
        reminder is unschedulable: a bad cron, a missing or malformed time, or a
        one-shot time already in the past."""
        reminder_id = reminder["id"]
        recurring = reminder.get("recurring")
        if recurring:
            try:
                trigger = cron_trigger(recurring)
            except ValueError as error:
                logger.warning("invalid cron for reminder %s: %s", reminder_id, error)
                return False
        else:
            try:
                when = datetime.fromisoformat(reminder["remind_at"])
            except (ValueError, TypeError) as error:
                logger.warning("invalid remind_at for reminder %s: %s", reminder_id, error)
                return False
            if when <= datetime.now():
                return False
            trigger = DateTrigger(run_date=when)
        self._scheduler.add_job(
            self._on_reminder, trigger, id=f"reminder_{reminder_id}",
            replace_existing=True, args=[reminder],
        )
        return True

    def cancel_reminder(self, reminder_id: int) -> None:
        """Remove a reminder's job if present (no error if it is already gone)."""
        self._remove_job(f"reminder_{reminder_id}")

    def schedule_briefing(self, briefing: dict) -> bool:
        """Queue one recurring briefing. Returns False on an invalid cron."""
        try:
            trigger = cron_trigger(briefing["cron"])
        except ValueError as error:
            logger.warning("invalid cron for briefing %s: %s", briefing["id"], error)
            return False
        self._scheduler.add_job(
            self._on_briefing, trigger, id=f"briefing_{briefing['id']}",
            replace_existing=True, args=[briefing],
        )
        return True

    def cancel_briefing(self, briefing_id: int) -> None:
        """Remove a briefing's job if present (no error if it is already gone)."""
        self._remove_job(f"briefing_{briefing_id}")

    def _remove_job(self, job_id: str) -> None:
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass
