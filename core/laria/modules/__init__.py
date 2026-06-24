"""Domain modules: bundles of tools the engine exposes to the language model.

Each module knows how to register its tools on a ``ToolRegistry``. The engine
stays generic; an app decides which domains to switch on by calling the
matching ``register_*`` function.
"""
from __future__ import annotations

from .finance import register_finance_tools
from .food import register_food_tools
from .utilities import register_utilities_tools

__all__ = [
    "register_finance_tools",
    "register_food_tools",
    "register_utilities_tools",
]
