"""Finance storage tests on a temp DB (no Home Assistant, no network)."""
from __future__ import annotations

import os

import pytest

from laria.config import reload_settings
from laria.storage import finance, init_db


@pytest.fixture
async def db(tmp_path):
    os.environ["LARIA_DB_PATH"] = str(tmp_path / "test.db")
    os.environ["LARIA_DATA_DIR"] = str(tmp_path)
    reload_settings()
    await init_db()
    yield
    os.environ.pop("LARIA_DB_PATH", None)
    os.environ.pop("LARIA_DATA_DIR", None)
    reload_settings()


async def test_default_categories_seeded(db):
    cats = await finance.list_categories()
    assert "groceries" in cats
    assert finance.CATEGORY_TRANSFER in cats


async def test_account_crud(db):
    await finance.add_account("checking", "bank", opening_balance=100.0)
    acc = await finance.get_account("checking")
    assert acc["type"] == "bank"
    assert acc["owner"] == "family"

    assert await finance.update_account("checking", owner="alice") is True
    assert (await finance.get_account("checking"))["owner"] == "alice"

    # deletable while empty
    assert (await finance.delete_account("checking"))["ok"] is True
    assert await finance.get_account("checking") is None


async def test_balance_and_transactions(db):
    await finance.add_account("checking", "bank", opening_balance=50.0)
    await finance.add_transaction("checking", "2026-01-10", -20.0, "groceries", "shop")
    await finance.add_transaction("checking", "2026-01-15", 200.0, "salary")
    assert await finance.get_balance("checking") == 230.0

    txs = await finance.list_transactions(account="checking")
    assert len(txs) == 2

    # account with transactions is not hard-deleted
    res = await finance.delete_account("checking")
    assert res["ok"] is False and res["in_use"] is True


async def test_rules_apply(db):
    await finance.add_account("checking", "bank")
    await finance.add_transaction("checking", "2026-01-01", -10.0, "misc", "ESSO FUEL STATION")
    await finance.add_rule("esso", "fuel")
    n = await finance.apply_rule("esso")
    assert n == 1
    txs = await finance.list_transactions(category="fuel")
    assert len(txs) == 1


async def test_category_rename_merge(db):
    await finance.add_account("checking", "bank")
    await finance.add_transaction("checking", "2026-01-01", -5.0, "leisure")
    await finance.rename_category("leisure", "fun")
    assert (await finance.list_transactions(category="fun"))
    await finance.add_transaction("checking", "2026-01-02", -3.0, "shopping")
    await finance.merge_category("shopping", "fun")
    assert len(await finance.list_transactions(category="fun")) == 2
    # transfer category is protected
    assert await finance.rename_category("transfer", "x") is False


async def test_budget_status(db):
    await finance.add_account("checking", "bank")
    await finance.set_budget("groceries", 100.0)
    await finance.add_transaction("checking", "2026-03-05", -120.0, "groceries")
    status = await finance.get_budget_status(2026, 3)
    assert status[0]["category"] == "groceries"
    assert status[0]["over"] is True
    assert status[0]["spent"] == 120.0


async def test_goals(db):
    await finance.set_goal("vacation", 1000.0)
    res = await finance.add_to_goal("vacation", 250.0)
    assert res["saved"] == 250.0 and res["reached"] is False
    goals = await finance.get_goals()
    assert goals[0]["remaining"] == 750.0
    # floored at 0
    res = await finance.add_to_goal("vacation", -500.0)
    assert res["saved"] == 0.0


async def test_import_dedup(db):
    await finance.add_account("checking", "bank")
    movements = [
        {"date": "2026-01-01", "amount": -10.0, "description": "a", "hash": "h1"},
        {"date": "2026-01-02", "amount": -20.0, "description": "b", "hash": "h2"},
    ]
    r1 = await finance.import_transactions("checking", movements)
    assert r1["inserted"] == 2
    r2 = await finance.import_transactions("checking", movements)
    assert r2["inserted"] == 0 and r2["duplicates"] == 2


async def test_reports(db):
    await finance.add_account("checking", "bank")
    await finance.add_transaction("checking", "2026-01-10", 1000.0, "salary")
    await finance.add_transaction("checking", "2026-01-12", -300.0, "groceries")
    await finance.add_transaction("checking", "2026-01-20", -50.0, finance.CATEGORY_TRANSFER)

    summary = await finance.expense_summary()
    assert summary["income"] == 1000.0
    assert summary["expenses"] == -300.0  # transfer excluded
    assert summary["net"] == 700.0

    trend = await finance.monthly_trend(2026)
    assert trend[0]["income"] == 1000.0
    assert trend[0]["expenses"] == 300.0

    matrix = await finance.monthly_category_matrix()
    assert "groceries" in matrix["categories"]
    assert 2026 in await finance.years_with_data()
