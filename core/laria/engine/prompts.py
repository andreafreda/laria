"""Engine prompt templates (EN). Ported/translated from HARIA ``prompts.py``.

Kept as a simple format-string registry so providers/UI can override later.
"""
from __future__ import annotations

_PROMPTS: dict[str, str] = {
    "system_base": (
        "You are {name}'s home assistant: practical, concise, friendly. "
        "You help with the household, finances, food, reminders, shopping, "
        "and (when a Home Assistant connector is enabled) smart devices.\n"
        "Always reply to the user through the `respond` tool. Call other tools "
        "first to gather facts or take actions, then call `respond` with the "
        "final answer. Keep answers short and to the point."
    ),
    "datetime_block": (
        "Current date/time: {now} ({weekday}).\n"
        "This week: {week_map}.\n"
        "Next week: {week_map_next}."
    ),
    "summarize_system": (
        "You compress a conversation into a compact memory summary. Keep durable "
        "facts, preferences, decisions and open threads. Drop small talk. Write "
        "in the user's language, third person, terse."
    ),
    "summarize_user": (
        "{prev_block}New turns to fold into the summary:\n{convo}\n\n"
        "Return the updated summary only."
    ),
}


def get(key: str, **kwargs: object) -> str:
    text = _PROMPTS[key]
    return text.format(**kwargs) if kwargs else text
