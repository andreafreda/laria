"""Finance domain storage: accounts, transactions, categories, rules, budgets,
goals and reports.

Split into one module per concept; this package re-exports the whole public API
so callers keep using a single namespace:

    from laria.storage import finance
    await finance.add_account(...)
    await finance.expense_summary(...)
"""
from __future__ import annotations

from ..db import CATEGORY_TRANSFER
from .accounts import (
    add_account,
    delete_account,
    get_account,
    list_accounts,
    update_account,
)
from .budgets import (
    delete_budget,
    get_budget_status,
    list_budgets,
    set_budget,
)
from .categories import (
    delete_category,
    list_categories,
    merge_category,
    normalize_category,
    rename_category,
)
from .goals import (
    add_to_goal,
    delete_goal,
    get_goals,
    set_goal,
)
from .reports import (
    balances_by_owner,
    category_spending_year,
    expense_summary,
    get_balances,
    month_transactions,
    monthly_category_matrix,
    monthly_trend,
    recent_transactions,
    reset_finance,
    years_with_data,
)
from .rules import (
    add_rule,
    apply_rule,
    apply_rules,
    delete_rule,
    list_rules,
    match_rule,
)
from .transactions import (
    add_transaction,
    delete_transaction,
    get_balance,
    import_transactions,
    list_transactions,
    update_transaction,
)

__all__ = [
    "CATEGORY_TRANSFER",
    # accounts
    "list_accounts", "get_account", "add_account", "update_account", "delete_account",
    # transactions
    "add_transaction", "get_balance", "list_transactions",
    "update_transaction", "delete_transaction", "import_transactions",
    # rules
    "add_rule", "delete_rule", "list_rules", "match_rule", "apply_rule", "apply_rules",
    # categories
    "list_categories", "normalize_category", "delete_category",
    "rename_category", "merge_category",
    # budgets
    "set_budget", "delete_budget", "list_budgets", "get_budget_status",
    # goals
    "set_goal", "add_to_goal", "delete_goal", "get_goals",
    # reports
    "reset_finance", "get_balances", "balances_by_owner", "expense_summary",
    "monthly_trend", "category_spending_year", "years_with_data",
    "monthly_category_matrix", "recent_transactions", "month_transactions",
]
