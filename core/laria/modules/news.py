"""News briefing tools and the briefing generator.

A briefing is a set of topics plus a cron schedule. At each scheduled time the
assistant searches the web for every topic, summarizes the findings with the
configured LLM, and sends the result (delivery is handled by the notifier, not
here). Users manage briefings and a personal source blocklist through the tools
registered by ``register_news_tools``.

Topics are stored as JSON, e.g.
``[{"topic": "ai", "sources": ["wired.com"]}, {"topic": "markets"}]``.
A per-topic ``sources`` whitelist limits that topic to those domains; the
per-user blocklist excludes domains from every topic.
"""
from __future__ import annotations

import json
import logging

from ..engine.tools import Tool, ToolContext, ToolRegistry
from ..llm import LLMProvider
from ..scheduler import Scheduler
from ..services import web_search
from ..storage import misc

logger = logging.getLogger(__name__)

_DEFAULT_RESULTS_PER_TOPIC = 5

_BRIEFING_PROMPT = (
    "You are a concise news editor. Summarize the search results below into a "
    "short briefing in the user's language. Group by topic, keep at most {max_news} "
    "items per topic, one short line each with the key fact. Skip duplicates and "
    "anything with no real news. Do not invent facts.\n\n{raw}"
)


def _parse_topics(topics: str) -> list[dict]:
    """Read the stored topics field into a list of ``{topic, sources}``.

    Accepts the JSON shape and, for older rows, a plain comma-separated string.
    """
    if not topics:
        return []
    try:
        data = json.loads(topics)
    except (ValueError, TypeError):
        data = None
    if isinstance(data, list):
        parsed = []
        for item in data:
            if isinstance(item, dict) and item.get("topic"):
                parsed.append({
                    "topic": str(item["topic"]).strip(),
                    "sources": [s.strip().lower() for s in item.get("sources", []) if s.strip()],
                })
            elif isinstance(item, str) and item.strip():
                parsed.append({"topic": item.strip(), "sources": []})
        return parsed
    return [{"topic": t.strip(), "sources": []} for t in topics.split(",") if t.strip()]


def _dump_topics(topics) -> str:
    """Serialize topics from a tool call into the normalized JSON we store."""
    normalized = []
    for item in topics or []:
        if isinstance(item, dict) and item.get("topic"):
            normalized.append({
                "topic": str(item["topic"]).strip(),
                "sources": [s.strip().lower() for s in item.get("sources", []) if s.strip()],
            })
        elif isinstance(item, str) and item.strip():
            normalized.append({"topic": item.strip(), "sources": []})
    return json.dumps(normalized, ensure_ascii=False)


def _build_query(topic: str, sources: list[str], blocks: list[str]) -> str:
    """Compose a search query for one topic, applying source whitelist/blocklist."""
    query = f"{topic} latest news"
    if sources:
        query += " (" + " OR ".join(f"site:{s}" for s in sources) + ")"
    for blocked in blocks:
        query += f" -site:{blocked}"
    return query


async def generate(provider: LLMProvider, topics: str, user_id: str = "",
                   num_news: int = _DEFAULT_RESULTS_PER_TOPIC) -> str:
    """Search every topic and return a short summarized briefing.

    ``num_news`` is the maximum number of items per topic; fewer are shown when
    fewer are found. When no topic returns anything, a plain message is returned
    without calling the LLM. The user's source blocklist is applied to every
    query.
    """
    items = _parse_topics(topics)
    if not items:
        return "No topics configured for the briefing."
    try:
        max_items = max(1, int(num_news))
    except (TypeError, ValueError):
        max_items = _DEFAULT_RESULTS_PER_TOPIC

    blocks = await misc.get_news_blocks(user_id) if user_id else []
    topic_blocks: list[str] = []
    empty_topics: list[str] = []
    for item in items:
        query = _build_query(item["topic"], item.get("sources", []), blocks)
        results = await web_search.search_news(query, max_items)
        if not results:  # fall back to general search when the news endpoint is empty
            results = await web_search.search(query, max_items)
        if not results:
            empty_topics.append(item["topic"])
            continue
        topic_blocks.append(_format_topic(item["topic"], results))

    if not topic_blocks:
        joined = ", ".join(empty_topics)
        return f"No news found for: {joined}." if joined else "No news found."

    raw = "\n\n".join(topic_blocks)
    prompt = _BRIEFING_PROMPT.format(max_news=max_items, raw=raw)
    response = await provider.generate(
        system="", messages=[{"role": "user", "content": prompt}], max_tokens=900,
    )
    summary = response.text.strip()
    return summary or raw


def _format_topic(topic: str, results: list[dict]) -> str:
    """Render one topic's search hits into the text block fed to the summarizer."""
    lines = [f"# Topic: {topic}"]
    for result in results:
        title = result.get("title") or ""
        snippet = result.get("snippet") or ""
        url = result.get("url") or ""
        meta = " | ".join(x for x in (result.get("date") or "", result.get("source") or "") if x)
        lines.append(f"- {title}\n  {meta}\n  {snippet} ({url})")
    return "\n".join(lines)


_TOPICS_SCHEMA = {
    "type": "array",
    "description": "Topics to follow. Each has a name and an optional per-topic source whitelist.",
    "items": {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Topic or keyword"},
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional domains allowed for this topic only (e.g. ['wired.com']).",
            },
        },
        "required": ["topic"],
    },
}


def register_news_tools(registry: ToolRegistry, provider: LLMProvider,
                        scheduler: Scheduler | None = None) -> None:
    """Add news briefing and source-blocklist tools to the registry.

    ``scheduler`` is optional: when present, created or edited briefings are
    scheduled live; when absent (for example in a web-only process) they are
    saved and picked up the next time a scheduler loads active briefings.
    """

    async def _create_briefing(inputs: dict, ctx: ToolContext) -> str:
        topics_json = _dump_topics(inputs["topics"])
        briefing = await misc.add_briefing(
            ctx.user_id, topics_json, inputs["cron"], int(inputs.get("num_news") or 5))
        if scheduler is not None and not scheduler.schedule_briefing(briefing):
            await misc.deactivate_briefing(briefing["id"], ctx.user_id)
            return json.dumps({"ok": False, "error": "invalid cron"}, ensure_ascii=False)
        return json.dumps({"ok": True, "briefing": briefing}, ensure_ascii=False)

    async def _list_briefings(inputs: dict, ctx: ToolContext) -> str:
        items = await misc.get_user_briefings(ctx.user_id)
        for item in items:
            item["topics"] = _parse_topics(item["topics"])
        return json.dumps(items, ensure_ascii=False) if items else "No briefings configured."

    async def _update_briefing(inputs: dict, ctx: ToolContext) -> str:
        topics_json = _dump_topics(inputs["topics"]) if "topics" in inputs else None
        num_news = int(inputs["num_news"]) if inputs.get("num_news") is not None else None
        briefing = await misc.update_briefing(
            int(inputs["id"]), ctx.user_id, topics_json, inputs.get("cron"), num_news)
        if not briefing:
            return json.dumps({"ok": False, "error": "briefing not found"}, ensure_ascii=False)
        if scheduler is not None:
            scheduler.cancel_briefing(briefing["id"])
            scheduler.schedule_briefing(briefing)
        return json.dumps({"ok": True, "briefing": briefing}, ensure_ascii=False)

    async def _delete_briefing(inputs: dict, ctx: ToolContext) -> str:
        deleted = await misc.deactivate_briefing(int(inputs["id"]), ctx.user_id)
        if deleted and scheduler is not None:
            scheduler.cancel_briefing(int(inputs["id"]))
        return json.dumps({"ok": deleted, "id": inputs["id"]}, ensure_ascii=False)

    async def _block_source(inputs: dict, ctx: ToolContext) -> str:
        ok = await misc.add_news_block(ctx.user_id, inputs["domain"])
        return json.dumps({"ok": ok, "domain": inputs.get("domain")}, ensure_ascii=False)

    async def _unblock_source(inputs: dict, ctx: ToolContext) -> str:
        ok = await misc.remove_news_block(ctx.user_id, inputs["domain"])
        return json.dumps({"ok": ok, "domain": inputs.get("domain")}, ensure_ascii=False)

    async def _list_sources(inputs: dict, ctx: ToolContext) -> str:
        return json.dumps({"blocklist": await misc.get_news_blocks(ctx.user_id)}, ensure_ascii=False)

    registry.register(Tool(
        name="create_briefing",
        description=("Create a recurring news briefing. Searches the given topics on the web and "
                     "sends a summary at the cron times. Convert the user's requested time to cron."),
        input_schema={
            "type": "object",
            "properties": {
                "topics": _TOPICS_SCHEMA,
                "cron": {"type": "string", "description": "Standard 5-field cron (min hour day month day-of-week)"},
                "num_news": {"type": "integer", "description": "Max items per topic (default 5)."},
            },
            "required": ["topics", "cron"],
        },
        handler=_create_briefing,
    ))
    registry.register(Tool(
        name="list_briefings",
        description="List the current user's configured news briefings (id, topics, sources, cron).",
        input_schema={"type": "object", "properties": {}},
        handler=_list_briefings,
    ))
    registry.register(Tool(
        name="update_briefing",
        description=("Edit a briefing by id. Pass topics (the full replacement list) and/or cron. "
                     "To drop a topic, resend topics without it."),
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "topics": _TOPICS_SCHEMA,
                "cron": {"type": "string"},
                "num_news": {"type": "integer", "description": "Max items per topic."},
            },
            "required": ["id"],
        },
        handler=_update_briefing,
    ))
    registry.register(Tool(
        name="delete_briefing",
        description="Delete a news briefing by id.",
        input_schema={"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
        handler=_delete_briefing,
    ))
    registry.register(Tool(
        name="block_news_source",
        description=("Block a domain from all of the user's news (permanent, global blocklist). "
                     "Pass the domain, e.g. 'example.com'."),
        input_schema={
            "type": "object",
            "properties": {"domain": {"type": "string", "description": "Domain to block, e.g. example.com"}},
            "required": ["domain"],
        },
        handler=_block_source,
    ))
    registry.register(Tool(
        name="unblock_news_source",
        description="Remove a domain from the user's news blocklist.",
        input_schema={
            "type": "object",
            "properties": {"domain": {"type": "string"}},
            "required": ["domain"],
        },
        handler=_unblock_source,
    ))
    registry.register(Tool(
        name="list_news_sources",
        description="List the domains in the user's news blocklist.",
        input_schema={"type": "object", "properties": {}},
        handler=_list_sources,
    ))
