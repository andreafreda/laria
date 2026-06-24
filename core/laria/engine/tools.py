"""Tool registry, the engine's extension seam.

Tools are vendor-neutral: each carries a JSON-schema (``{name, description,
input_schema}``) the LLM sees, plus an async handler. Domain modules and the
optional HA connector register their tools here; the engine never hard-codes
them. This replaces HARIA's ``modules.tools()/owns()/dispatch()`` plus the
HA-specific core tools baked into the engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from ..memory import MemoryBackend, Scope

# A handler receives the tool inputs and a context, returns a string result.
Handler = Callable[[dict[str, Any], "ToolContext"], Awaitable[str]]


@dataclass
class ToolContext:
    """Everything a tool handler may need, passed per call."""
    user_id: str
    memory: MemoryBackend
    scope: Scope
    user_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler

    def schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description,
                "input_schema": self.input_schema}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def owns(self, name: str) -> bool:
        return name in self._tools

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    async def dispatch(self, name: str, inputs: dict[str, Any], ctx: ToolContext) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Unknown tool: {name}"
        return await tool.handler(inputs, ctx)
