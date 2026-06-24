"""Finance tools the assistant can call during a conversation.

Each tool is a thin bridge between the language model and ``storage.finance``:
it validates nothing beyond what the schema enforces, calls one storage
function, and returns a short result for the model to read back to the user.
Register them on an engine's tool registry with ``register_finance_tools``.

Handlers return a string because that is what the model consumes: a JSON blob
for data it should reason over, or a plain sentence to confirm an action.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from ..engine.tools import Tool, ToolContext, ToolRegistry
from ..storage import finance


async def _add_transaction(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Record one income or expense and confirm it back to the user."""
    when = inputs.get("date") or date.today().isoformat()
    await finance.add_transaction(
        account=inputs["account"],
        date=when,
        amount=float(inputs["amount"]),
        category=inputs["category"],
        description=inputs.get("description", ""),
    )
    return f"Recorded {inputs['amount']} in '{inputs['category']}' on {when}."


async def _list_recent_transactions(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Return recent transactions as JSON, optionally filtered by category."""
    rows = await finance.list_transactions(
        category=inputs.get("category"),
        limit=int(inputs.get("limit", 20)),
    )
    return json.dumps(rows, ensure_ascii=False)


async def _get_balances(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Return the current balance of every active account as JSON."""
    return json.dumps(await finance.get_balances(), ensure_ascii=False)


async def _expense_summary(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Return income, expenses, net and a per-category breakdown for a period."""
    summary = await finance.expense_summary(
        date_from=inputs.get("date_from"),
        date_to=inputs.get("date_to"),
    )
    return json.dumps(summary, ensure_ascii=False)


async def _set_budget(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Set the monthly budget for a category and confirm it."""
    category = await finance.set_budget(inputs["category"], float(inputs["amount"]))
    return f"Budget for '{category}' set to {inputs['amount']} per month."


async def _budget_status(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Return how each budgeted category is tracking for a given month as JSON."""
    today = date.today()
    status = await finance.get_budget_status(
        year=int(inputs.get("year", today.year)),
        month=int(inputs.get("month", today.month)),
    )
    return json.dumps(status, ensure_ascii=False)


async def _list_goals(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Return all savings goals with their progress as JSON."""
    return json.dumps(await finance.get_goals(), ensure_ascii=False)


async def _add_to_goal(inputs: dict[str, Any], ctx: ToolContext) -> str:
    """Add money to a savings goal and report its new state."""
    result = await finance.add_to_goal(inputs["name"], float(inputs["amount"]))
    if result is None:
        return f"No savings goal named '{inputs['name']}'."
    return json.dumps(result, ensure_ascii=False)


def register_finance_tools(registry: ToolRegistry) -> None:
    """Add the finance tools to a registry so the engine exposes them to the model."""
    registry.register(Tool(
        name="add_transaction",
        description=("Record a money movement. Amount is signed: positive for "
                     "income, negative for an expense. Date is YYYY-MM-DD and "
                     "defaults to today if omitted."),
        input_schema={
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account name the movement belongs to"},
                "amount": {"type": "number", "description": "Signed amount: + income, - expense"},
                "category": {"type": "string", "description": "Spending/income category"},
                "date": {"type": "string", "description": "YYYY-MM-DD (defaults to today)"},
                "description": {"type": "string", "description": "Free-text note"},
            },
            "required": ["account", "amount", "category"],
        },
        handler=_add_transaction,
    ))
    registry.register(Tool(
        name="list_recent_transactions",
        description="List recent transactions, newest first, optionally one category.",
        input_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filter to this category"},
                "limit": {"type": "integer", "description": "How many to return (default 20)"},
            },
        },
        handler=_list_recent_transactions,
    ))
    registry.register(Tool(
        name="get_balances",
        description="Get the current balance of every active account.",
        input_schema={"type": "object", "properties": {}},
        handler=_get_balances,
    ))
    registry.register(Tool(
        name="expense_summary",
        description=("Summarize income, expenses and net for a period, with a "
                     "per-category expense breakdown. Dates are YYYY-MM-DD and "
                     "both are optional."),
        input_schema={
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
            },
        },
        handler=_expense_summary,
    ))
    registry.register(Tool(
        name="set_budget",
        description="Set the monthly spending budget for a category.",
        input_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category to budget"},
                "amount": {"type": "number", "description": "Monthly cap (positive)"},
            },
            "required": ["category", "amount"],
        },
        handler=_set_budget,
    ))
    registry.register(Tool(
        name="budget_status",
        description=("Show how each budgeted category is tracking for a month "
                     "(spent, remaining, over). Year and month default to now."),
        input_schema={
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Year (defaults to current)"},
                "month": {"type": "integer", "description": "Month 1-12 (defaults to current)"},
            },
        },
        handler=_budget_status,
    ))
    registry.register(Tool(
        name="list_goals",
        description="List savings goals with target, saved amount and progress.",
        input_schema={"type": "object", "properties": {}},
        handler=_list_goals,
    ))
    registry.register(Tool(
        name="add_to_goal",
        description="Add money to a savings goal (use a negative amount to withdraw).",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Goal name"},
                "amount": {"type": "number", "description": "Amount to add (negative to withdraw)"},
            },
            "required": ["name", "amount"],
        },
        handler=_add_to_goal,
    ))
