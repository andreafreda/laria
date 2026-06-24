"""HTTP JSON API: the standalone channel for talking to the engine."""
from __future__ import annotations

from .app import create_app

__all__ = ["create_app"]
