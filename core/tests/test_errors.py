"""Central error reporting tests on a temp DB (HA disabled, no notification)."""
from __future__ import annotations

import os

import pytest

from laria.config import reload_settings
from laria.errors import report_error
from laria.storage import init_db, misc


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


async def test_report_error_writes_log_with_traceback(db):
    try:
        raise ValueError("boom")
    except ValueError as error:
        await report_error("telegram", "handling failed", error, notify_ha=False)

    logs = await misc.get_error_logs(10)
    assert logs[0]["source"] == "telegram"
    assert logs[0]["message"] == "handling failed"
    assert "ValueError: boom" in logs[0]["traceback"]


async def test_report_error_without_exception(db):
    await report_error("web", "something off", notify_ha=False)
    logs = await misc.get_error_logs(10)
    assert logs[0]["message"] == "something off"
    assert logs[0]["traceback"] is None
