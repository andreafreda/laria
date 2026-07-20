"""Domain modules: bundles of tools the engine exposes to the language model.

Each module knows how to register its tools on a ``ToolRegistry``. The engine
stays generic; an app decides which domains to switch on by calling the
matching ``register_*`` function.
"""
from __future__ import annotations

from .events import register_events_tools
from .finance import register_finance_tools
from .food import register_food_tools
from .lists import register_lists_tools
from .news import register_news_tools
from .reminders import register_reminders_tools
from .utilities import register_utilities_tools

__all__ = [
    "register_events_tools",
    "register_finance_tools",
    "register_food_tools",
    "register_lists_tools",
    "register_news_tools",
    "register_reminders_tools",
    "register_utilities_tools",
]
