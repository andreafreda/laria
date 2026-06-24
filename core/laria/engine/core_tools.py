"""Built-in, connector-independent tools: explicit notes + semantic recall.

HA-specific tools (house state, device control, Alexa) are intentionally NOT
here — they live in the HA connector and register themselves when enabled.
``respond`` is handled by the engine loop itself, not dispatched here.
"""
from __future__ import annotations

import json
from typing import Any

from ..storage import conversations
from .tools import Tool, ToolContext, ToolRegistry


async def _get_memory(inputs: dict[str, Any], ctx: ToolContext) -> str:
    notes = await conversations.get_notes(ctx.user_id)
    return json.dumps(notes, ensure_ascii=False) if notes else "No saved notes."


async def _save_memory(inputs: dict[str, Any], ctx: ToolContext) -> str:
    key, value = inputs["key"], inputs["value"]
    await conversations.save_note(ctx.user_id, key, value)
    # Also index it in semantic memory so `recall` can find it later.
    ctx.memory.write(ctx.scope, f"{key}: {value}", source="user")
    return f"Note '{key}' saved."


async def _recall(inputs: dict[str, Any], ctx: ToolContext) -> str:
    items = ctx.memory.recall(ctx.scope, inputs.get("query", ""), k=5)
    if not items:
        return "Nothing recalled."
    return json.dumps([i.text for i in items], ensure_ascii=False)


def register_core_tools(registry: ToolRegistry) -> None:
    registry.register(Tool(
        name="get_memory",
        description="Retrieve saved notes/preferences for the current user.",
        input_schema={"type": "object", "properties": {}},
        handler=_get_memory,
    ))
    registry.register(Tool(
        name="save_memory",
        description=("Save a note/preference for the current user. Use a short, "
                     "descriptive key."),
        input_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Short key (e.g. 'morning_meds')"},
                "value": {"type": "string", "description": "Value to store"},
            },
            "required": ["key", "value"],
        },
        handler=_save_memory,
    ))
    registry.register(Tool(
        name="recall",
        description=("Search long-term memory for older facts not in the recent "
                     "context. Use when the user refers to something said long ago."),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to search for"},
            },
            "required": ["query"],
        },
        handler=_recall,
    ))
