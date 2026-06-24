"""Utility-bill tools the assistant can call during a conversation.

Thin bridges between the language model and ``storage.utilities``: record a
month's consumption or cost, spread a bill over a range of months, and read a
year back. Register them with ``register_utilities_tools``.

A bill row is identified by (utility, metric, year, month). ``metric`` is
'kwh' or 'm3' for consumption, or 'cost' for money.
"""
from __future__ import annotations

import json
from typing import Any

from ..engine.tools import Tool, ToolContext, ToolRegistry
from ..storage import utilities


async def _record_bill(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Record a single month's value for a utility metric and confirm it."""
    await utilities.set_bill(
        utility=inputs["utility"],
        metric=inputs["metric"],
        year=int(inputs["year"]),
        month=int(inputs["month"]),
        value=float(inputs["value"]),
    )
    return (f"Recorded {inputs['utility']} {inputs['metric']} "
            f"{inputs['value']} for {inputs['year']}-{int(inputs['month']):02d}.")


async def _record_bill_range(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Spread a total evenly across a range of months and confirm it."""
    await utilities.set_bill_range(
        utility=inputs["utility"],
        metric=inputs["metric"],
        year=int(inputs["year"]),
        m_start=int(inputs["month_start"]),
        m_end=int(inputs["month_end"]),
        total=float(inputs["total"]),
    )
    return (f"Spread {inputs['total']} of {inputs['utility']} {inputs['metric']} "
            f"over months {inputs['month_start']} to {inputs['month_end']} of {inputs['year']}.")


async def _get_bill_year(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Return the twelve monthly values for a utility metric in a year as JSON.

    Months with no data read as 0. Index 0 is January.
    """
    csv = await utilities.get_bill_csv(
        utility=inputs["utility"],
        metric=inputs["metric"],
        year=int(inputs["year"]),
    )
    monthly_values = [float(value) for value in csv.split(",")]
    return json.dumps(monthly_values, ensure_ascii=False)


_UTILITY = {"type": "string", "description": "Utility name, e.g. power, gas, water"}
_METRIC = {"type": "string", "description": "'kwh' or 'm3' for consumption, 'cost' for money"}


def register_utilities_tools(registry: ToolRegistry) -> None:
    """Add the utility-bill tools to a registry so the engine exposes them."""
    registry.register(Tool(
        name="record_bill",
        description="Record one month's consumption or cost for a utility.",
        input_schema={
            "type": "object",
            "properties": {
                "utility": _UTILITY,
                "metric": _METRIC,
                "year": {"type": "integer"},
                "month": {"type": "integer", "description": "1-12"},
                "value": {"type": "number"},
            },
            "required": ["utility", "metric", "year", "month", "value"],
        },
        handler=_record_bill,
    ))
    registry.register(Tool(
        name="record_bill_range",
        description=("Spread a single bill total evenly across a range of months "
                     "(for a bill that covers several months at once)."),
        input_schema={
            "type": "object",
            "properties": {
                "utility": _UTILITY,
                "metric": _METRIC,
                "year": {"type": "integer"},
                "month_start": {"type": "integer", "description": "First month 1-12"},
                "month_end": {"type": "integer", "description": "Last month 1-12"},
                "total": {"type": "number", "description": "Total to spread evenly"},
            },
            "required": ["utility", "metric", "year", "month_start", "month_end", "total"],
        },
        handler=_record_bill_range,
    ))
    registry.register(Tool(
        name="get_bill_year",
        description="Get the twelve monthly values for a utility metric in a year.",
        input_schema={
            "type": "object",
            "properties": {
                "utility": _UTILITY,
                "metric": _METRIC,
                "year": {"type": "integer"},
            },
            "required": ["utility", "metric", "year"],
        },
        handler=_get_bill_year,
    ))
