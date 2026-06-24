"""Provider-agnostic agentic engine.

Ported from HARIA ``claude_engine.py`` but decoupled: the LLM is any
``laria.llm.LLMProvider``, tools come from a ``ToolRegistry`` (HA tools optional
via the connector), conversation history from ``storage.conversations``, and
semantic recall from a ``MemoryBackend``. The loop runs until the model calls
``respond``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from ..config import Settings, get_settings
from ..llm import LLMProvider, LLMResponse, TextBlock, ToolUseBlock
from ..memory import MemoryBackend, Scope
from ..storage import conversations as conv
from . import prompts
from .core_tools import register_core_tools
from .tools import ToolContext, ToolRegistry

logger = logging.getLogger(__name__)

RESPOND_TOOL = {
    "name": "respond",
    "description": "Reply to the user with a text message. Use this for all replies.",
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The reply text for the user."},
        },
        "required": ["text"],
    },
}

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]


def _blocks_to_content(blocks: list[TextBlock | ToolUseBlock]) -> list[dict[str, Any]]:
    """Rebuild a vendor-neutral assistant message from normalized blocks."""
    out: list[dict[str, Any]] = []
    for b in blocks:
        if isinstance(b, TextBlock):
            out.append({"type": "text", "text": b.text})
        elif isinstance(b, ToolUseBlock):
            out.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    return out


class Engine:
    def __init__(self, provider: LLMProvider, memory: MemoryBackend, *,
                 registry: ToolRegistry | None = None, settings: Settings | None = None,
                 max_turns: int = 8):
        self.provider = provider
        self.memory = memory
        self.settings = settings or get_settings()
        self.registry = registry or ToolRegistry()
        register_core_tools(self.registry)
        self.model = self.settings.llm.model
        self.max_tokens = self.settings.llm.max_tokens
        self.max_turns = max_turns

    def _tools(self) -> list[dict[str, Any]]:
        schemas = self.registry.schemas()
        respond = dict(RESPOND_TOOL)
        if self.provider.supports_prompt_cache():
            # Cache the whole (static) tools block via the last tool.
            respond = {**respond, "cache_control": {"type": "ephemeral", "ttl": "1h"}}
        return schemas + [respond]

    async def _build_system(self, user_id: str, user_config: dict) -> list[dict[str, Any]]:
        name = user_config.get("name", "User")
        base = prompts.get("system_base", name=name)
        context = user_config.get("context", "")
        if context:
            base += f"\n\nUser context: {context}"

        # Volatile block (notes + summary): separate cache breakpoint so saving a
        # note doesn't invalidate the stable prefix.
        volatile = ""
        notes = await conv.get_notes(user_id)
        if notes:
            note_lines = "\n".join(f"- {k}: {v}" for k, v in notes.items())
            volatile += "USER MEMORY (saved notes, use them without calling get_memory):\n" + note_lines
        summary = await conv.get_summary(user_id)
        if summary:
            if volatile:
                volatile += "\n\n"
            volatile += "PREVIOUS CONVERSATION SUMMARY (historical context):\n" + summary

        now = datetime.now()
        monday = now.date() - timedelta(days=now.weekday())
        week_map = "; ".join(
            f"{_WEEKDAYS[i]}={(monday + timedelta(days=i)).isoformat()}" for i in range(7)
        )
        next_monday = monday + timedelta(days=7)
        week_map_next = "; ".join(
            f"{_WEEKDAYS[i]}={(next_monday + timedelta(days=i)).isoformat()}" for i in range(7)
        )
        dt_block = prompts.get(
            "datetime_block", now=now.isoformat(timespec="seconds"),
            weekday=_WEEKDAYS[now.weekday()], week_map=week_map, week_map_next=week_map_next,
        )

        cache = ({"cache_control": {"type": "ephemeral", "ttl": "1h"}}
                 if self.provider.supports_prompt_cache() else {})
        blocks = [{"type": "text", "text": base, **cache}]
        if volatile:
            blocks.append({"type": "text", "text": volatile, **cache})
        blocks.append({"type": "text", "text": dt_block})  # uncached (changes each call)
        return blocks

    async def _maybe_summarize(self, user_id: str) -> None:
        """Fold old turns into a rolling summary when history exceeds the window."""
        try:
            if await conv.count_history(user_id) <= conv.MAX_HISTORY + conv.SUMMARY_BATCH:
                return
            old = await conv.get_old_turns(user_id)
            if not old:
                return
            prev = await conv.get_summary(user_id)
            convo = "\n".join(f"{t['role']}: {t['content']}" for t in old)
            prev_block = f"Existing summary:\n{prev}\n\n" if prev else ""
            resp = await self.provider.generate(
                system=prompts.get("summarize_system"),
                messages=[{"role": "user", "content": prompts.get(
                    "summarize_user", prev_block=prev_block, convo=convo)}],
                max_tokens=400, model=self.model,
            )
            new_summary = resp.text.strip()
            if new_summary:
                await conv.set_summary(user_id, new_summary)
                await conv.delete_turns([t["id"] for t in old])
                logger.info("memory summary updated for %s (%d turns folded)", user_id, len(old))
        except Exception as e:  # best-effort
            logger.warning("summarize failed for %s: %s", user_id, e)

    async def chat(self, user_id: str, user_text: str,
                   user_config: dict | None = None) -> str:
        user_config = user_config or {}
        scope = Scope(user_id=user_id)
        ctx = ToolContext(user_id=user_id, memory=self.memory, scope=scope,
                          user_config=user_config)

        await self._maybe_summarize(user_id)
        history = await conv.get_history(user_id)
        await conv.save_turn(user_id, "user", user_text or "")

        messages: list[dict[str, Any]] = history + [{"role": "user", "content": user_text}]
        system = await self._build_system(user_id, user_config)

        for turn in range(self.max_turns):
            force_respond = turn == self.max_turns - 1
            response: LLMResponse = await self.provider.generate(
                system=system, messages=messages, tools=self._tools(),
                tool_choice=({"type": "tool", "name": "respond"} if force_respond
                             else {"type": "any"}),
                max_tokens=self.max_tokens, model=self.model,
            )

            tool_results: list[dict[str, Any]] = []
            reply: str | None = None
            respond_ids: list[str] = []

            for block in response.tool_uses:
                if block.name == "respond":
                    reply = block.input.get("text", "")
                    respond_ids.append(block.id)
                else:
                    result = await self.registry.dispatch(block.name, block.input, ctx)
                    tool_results.append({"type": "tool_result",
                                         "tool_use_id": block.id, "content": result})

            # respond called alongside other tools: defer it so the model sees the
            # other tools' results first.
            if reply is not None and tool_results:
                for rid in respond_ids:
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": rid,
                        "content": ("Reply deferred: review the other tool results "
                                    "first, then call respond again."),
                    })
                reply = None

            if reply is not None:
                await conv.save_turn(user_id, "assistant", reply)
                return reply

            if tool_results:
                messages.append({"role": "assistant", "content": _blocks_to_content(response.blocks)})
                messages.append({"role": "user", "content": tool_results})
                continue

            # No tools, no respond: fall back to any text the model produced.
            reply = response.text
            await conv.save_turn(user_id, "assistant", reply)
            return reply

        logger.warning("chat: reached max_turns without respond for %s", user_id)
        fallback = "I had trouble completing the request. Please try again."
        await conv.save_turn(user_id, "assistant", fallback)
        return fallback
