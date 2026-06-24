"""Ingestion: parse external files (bank statements, ...) into importable data."""
from __future__ import annotations

from . import bank_statements

__all__ = ["bank_statements"]
