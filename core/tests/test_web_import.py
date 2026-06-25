"""Bank-statement import endpoint tests (csv upload, temp DB, no network)."""
from __future__ import annotations

import os

import pytest
from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer

from laria import auth
from laria.config import reload_settings
from laria.storage import finance, init_db
from laria.web import create_app


def _auth_header() -> dict:
    user = {"id": 1, "username": "owner", "role": "owner",
            "profile_id": 1, "must_change_password": False}
    return {"Authorization": f"Bearer {auth.issue_token(user)}"}


@pytest.fixture
async def client(tmp_path):
    os.environ["LARIA_DB_PATH"] = str(tmp_path / "test.db")
    os.environ["LARIA_DATA_DIR"] = str(tmp_path)
    os.environ["LARIA_JWT_SECRET"] = "test-secret"
    reload_settings()
    await init_db()
    await finance.add_account("checking", "bank")

    test_client = TestClient(TestServer(create_app(engine=None)))
    await test_client.start_server()
    yield test_client

    await test_client.close()
    os.environ.pop("LARIA_DB_PATH", None)
    os.environ.pop("LARIA_DATA_DIR", None)
    os.environ.pop("LARIA_JWT_SECRET", None)
    reload_settings()


_POSTEPAY_CSV = (
    "Data;Importo;Descrizione\n"
    "2026-01-10;-9,99;NETFLIX\n"
    "2026-01-12;-30,00;ESSELUNGA\n"
).encode("utf-8")


def _upload(account: str, content: bytes, filename: str = "statement.csv") -> FormData:
    form = FormData()
    form.add_field("account", account)
    form.add_field("file", content, filename=filename, content_type="text/csv")
    return form


async def test_import_requires_auth(client):
    resp = await client.post("/api/finance/import",
                             data=_upload("checking", _POSTEPAY_CSV))
    assert resp.status == 401


async def test_import_csv(client):
    resp = await client.post("/api/finance/import",
                             data=_upload("checking", _POSTEPAY_CSV),
                             headers=_auth_header())
    assert resp.status == 200
    body = await resp.json()
    assert body["inserted"] == 2
    assert body["format"] == "postepay"
    assert len(await finance.list_transactions(account="checking")) == 2


async def test_import_is_idempotent(client):
    headers = _auth_header()
    await client.post("/api/finance/import",
                      data=_upload("checking", _POSTEPAY_CSV), headers=headers)
    resp = await client.post("/api/finance/import",
                             data=_upload("checking", _POSTEPAY_CSV), headers=headers)
    body = await resp.json()
    assert body["inserted"] == 0 and body["duplicates"] == 2


async def test_import_unknown_account_is_400(client):
    resp = await client.post("/api/finance/import",
                             data=_upload("savings", _POSTEPAY_CSV),
                             headers=_auth_header())
    assert resp.status == 400


async def test_import_unrecognized_format_is_400(client):
    resp = await client.post("/api/finance/import",
                             data=_upload("checking", b"foo,bar\n1,2\n"),
                             headers=_auth_header())
    assert resp.status == 400


async def test_import_missing_file_is_400(client):
    form = FormData()
    form.add_field("account", "checking")
    resp = await client.post("/api/finance/import", data=form, headers=_auth_header())
    assert resp.status == 400
