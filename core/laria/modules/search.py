"""Web search tool: lets the assistant look things up on the internet.

A thin bridge from the engine to the web_search service so the model can answer
questions that need fresh or external facts (a name day date, an opening time, a
current price) instead of guessing. Distinct from the news module, which uses
the same service only to build scheduled briefings.
"""
from __future__ import annotations

import json

from ..engine.tools import Tool, ToolContext, ToolRegistry
from ..services import web_search

_DEFAULT_RESULTS = 5
_MAX_RESULTS = 10


def register_search_tools(registry: ToolRegistry) -> None:
    """Add the on-demand web search tool to the registry."""

    async def _search_web(inputs: dict, ctx: ToolContext) -> str:
        query = (inputs.get("query") or "").strip()
        if not query:
            return "Provide a search query."
        try:
            count = max(1, min(_MAX_RESULTS, int(inputs.get("max_results") or _DEFAULT_RESULTS)))
        except (TypeError, ValueError):
            count = _DEFAULT_RESULTS
        results = await web_search.search(query, count)
        if not results:
            return f"No web results for: {query}"
        return json.dumps(results, ensure_ascii=False)

    registry.register(Tool(
        name="search_web",
        description=("Search the web for current or external facts the user asks about "
                     "(e.g. a saint's name day date, opening hours, a price). Returns "
                     "title, url and snippet for each hit; read them and answer."),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
                "max_results": {"type": "integer",
                                "description": f"How many results (1-{_MAX_RESULTS}, default {_DEFAULT_RESULTS})"},
            },
            "required": ["query"],
        },
        handler=_search_web,
    ))
