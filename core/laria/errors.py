"""Central error reporting: persist captured errors, optionally notify.

Channels call ``report_error`` when they catch an exception they do not want to
crash on. It records the error in the database (so the owner sees it on the
System log page) and, when a Home Assistant connector is configured, raises a
persistent notification in HA so a human notices without watching logs. Both
sinks are best effort: reporting an error must never raise a new one.
"""
from __future__ import annotations

import logging
import traceback as traceback_module

from .config import get_settings
from .storage import misc

logger = logging.getLogger(__name__)


async def report_error(source: str, message: str,
                       error: BaseException | None = None,
                       notify_ha: bool = True) -> None:
    """Record an error and, if HA is configured, surface it as a notification.

    ``source`` names where it happened (e.g. "telegram", "web"). ``error``, when
    given, is rendered to a traceback string and stored alongside the message.
    Never raises: a failure in either sink is logged and swallowed.
    """
    trace = None
    if error is not None:
        trace = "".join(traceback_module.format_exception(
            type(error), error, error.__traceback__))
    try:
        await misc.add_error_log(source, "error", message, trace)
    except Exception:
        logger.exception("failed to write error to the log")

    if notify_ha:
        await _notify_home_assistant(source, message)


async def _notify_home_assistant(source: str, message: str) -> None:
    """Best-effort persistent notification in HA, only when HA is enabled."""
    settings = get_settings()
    if not settings.ha.enabled:
        return
    try:
        from .connectors.ha import HaClient
        client = HaClient.from_settings(settings.ha)
        await client.call_service("persistent_notification", "create", {
            "title": f"LARIA error ({source})",
            "message": message,
        })
    except Exception:
        logger.exception("failed to send HA error notification")
