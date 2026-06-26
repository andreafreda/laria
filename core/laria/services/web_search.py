"""Web search over DuckDuckGo (the ddgs library).

Two entry points: ``search`` for general results and ``search_news`` for the
news endpoint (which also carries a publication date and source). Both return a
plain list of dicts and never raise: a network error or an empty result set both
come back as an empty list, so callers can treat "nothing found" and "lookup
failed" the same way. Queries may use the ``site:``/``-site:`` operators to keep
or exclude particular sources.
"""
from __future__ import annotations

import asyncio
import logging

from ddgs import DDGS

logger = logging.getLogger(__name__)

# Bias results toward Italian sources, matching the assistant's primary audience.
_REGION = "it-it"


def _is_no_results(error: Exception) -> bool:
    """Tell an empty result set apart from a real failure.

    ddgs raises in both cases, so we look at the message: "no results" is a
    legitimate empty answer, anything else is a network or rate-limit error
    worth logging louder.
    """
    return "no results" in str(error).lower()


def _log_failure(function_name: str, query: str, error: Exception) -> None:
    if _is_no_results(error):
        logger.info("%s: no results for %r", function_name, query)
    else:
        logger.warning("%s: failed for %r: %s", function_name, query, error)


def _search_text(query: str, max_results: int) -> list[dict]:
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, region=_REGION, max_results=max_results))
    except Exception as error:
        _log_failure("search", query, error)
        return []


async def search(query: str, max_results: int = 5) -> list[dict]:
    """General web search. Returns ``[{title, url, snippet}]`` (possibly empty).

    Runs the blocking ddgs call in a worker thread so the event loop stays free.
    """
    raw = await asyncio.to_thread(_search_text, query, max_results)
    return [
        {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
        for r in raw
    ]


def _search_news(query: str, max_results: int) -> list[dict]:
    try:
        with DDGS() as ddgs:
            return list(ddgs.news(query, region=_REGION, max_results=max_results))
    except Exception as error:
        _log_failure("search_news", query, error)
        return []


async def search_news(query: str, max_results: int = 5) -> list[dict]:
    """News search. Like ``search`` but each item also carries ``date`` and
    ``source`` from the news endpoint. Returns a possibly empty list."""
    raw = await asyncio.to_thread(_search_news, query, max_results)
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", "") or r.get("href", ""),
            "snippet": r.get("body", ""),
            "date": r.get("date", ""),
            "source": r.get("source", ""),
        }
        for r in raw
    ]
