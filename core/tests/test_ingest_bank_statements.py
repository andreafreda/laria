"""Bank-statement parser tests: pure logic, no files, no network."""
from __future__ import annotations

from laria.ingest import bank_statements as bank


def test_detect_and_parse_bancoposta():
    rows = [
        ["Estratto conto"],
        ["Data contabile", "Addebiti", "Accrediti", "Descrizione"],
        ["01/02/2026", "12,50", "", "ESSELUNGA MILANO"],
        ["03/02/2026", "", "1.500,00", "STIPENDIO ACME"],
    ]
    assert bank.detect_format(rows) == "bancoposta"
    result = bank.parse(rows)

    assert result["account"] == "bancoposta"
    assert result["skipped"] == 0
    spending, income = result["movements"]
    assert spending["amount"] == -12.5
    assert spending["category"] == "groceries"
    assert income["amount"] == 1500.0
    assert income["category"] == "salary"
    assert income["date"] == "2026-02-03"


def test_parse_postepay_signed_amount():
    rows = [
        ["Data", "Importo", "Descrizione"],
        ["2026-01-10", "-9,99", "NETFLIX"],
    ]
    result = bank.parse(rows)
    assert result["account"] == "postepay"
    movement = result["movements"][0]
    assert movement["amount"] == -9.99
    assert movement["category"] == "subscriptions"


def test_unrecognized_format():
    result = bank.parse([["foo", "bar"], ["1", "2"]])
    assert result["format"] is None
    assert "error" in result


def test_duplicate_rows_get_distinct_hashes():
    rows = [
        ["Data", "Importo", "Descrizione"],
        ["2026-01-01", "-5,00", "BAR"],
        ["2026-01-01", "-5,00", "BAR"],
    ]
    first, second = bank.parse(rows)["movements"]
    assert first["hash"] != second["hash"]
    # the first keeps the bare historical hash so re-import stays idempotent
    assert first["hash"] == bank.row_hash("postepay", "2026-01-01", -5.0, "BAR")


def test_invalid_date_is_skipped():
    rows = [
        ["Data", "Importo", "Descrizione"],
        ["31/02/2026", "-1,00", "IMPOSSIBLE DATE"],
        ["2026-01-01", "-1,00", "OK"],
    ]
    result = bank.parse(rows)
    assert result["skipped"] == 1
    assert len(result["movements"]) == 1


def test_amount_parsing_italian_format():
    assert bank._to_amount("1.234,56") == 1234.56
    assert bank._to_amount("-12,50") == -12.5
    assert bank._to_amount("") is None
    assert bank._to_amount(42) == 42.0
