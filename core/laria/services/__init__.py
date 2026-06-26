"""Services: logic that talks to external sources (nutrition lookups, ...)."""
from __future__ import annotations

from . import nutrition
from . import web_search

__all__ = ["nutrition", "web_search"]
