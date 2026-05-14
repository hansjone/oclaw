"""SA migration: tenant + bind_code."""

from __future__ import annotations

import pytest

from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "sa_tenant_bc.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def test_sa_tenant_crud(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("Acme")
    listed = s.list_tenants(limit=50)
    assert any(x["id"] == t["id"] for x in listed)
    assert s.delete_tenant(tenant_id=t["id"]) == 1
    assert s.delete_tenant(tenant_id=t["id"]) == 0


def test_sa_bind_code_list_and_consume(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("BindCo")
    s.create_bind_code(tenant_id=t["id"], role="member", code="CODE12345")
    rows = s.list_bind_codes(tenant_id=t["id"], limit=10)
    assert len(rows) == 1
    assert rows[0]["code"] == "CODE12345"
    assert rows[0]["used_at"] is None
    out = s.consume_bind_code(code="CODE12345", channel="wecom", external_user_id="wx-1", display_name="Ext")
    assert out is not None
    assert out["tenant_id"] == t["id"]
    rows2 = s.list_bind_codes(tenant_id=t["id"], limit=10)
    assert rows2[0]["used_at"] is not None
    assert rows2[0]["used_by_external_user_id"] == "wx-1"
    assert s.consume_bind_code(code="CODE12345", channel="wecom", external_user_id="wx-2") is None
