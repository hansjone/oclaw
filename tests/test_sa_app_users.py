"""SA migration: app_user create + lookups."""

from __future__ import annotations

import pytest

from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "sa_app_users.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def test_sa_create_user_username_suffix(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("UApp")
    u1 = s.create_user(tenant_id=t["id"], display_name="Same Name", role="member")
    u2 = s.create_user(tenant_id=t["id"], display_name="Same Name", role="member")
    assert u1["username"] != u2["username"]
    assert u2["username"].startswith(u1["username"])


def test_sa_get_user_by_id_and_username(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("GApp")
    u = s.create_user(tenant_id=t["id"], display_name="Lookup", role="owner")
    by_id = s.get_user_by_id(tenant_id=t["id"], user_id=u["id"])
    assert by_id is not None
    assert by_id["id"] == u["id"]
    by_un = s.get_user_by_username(tenant_id=t["id"], username=u["username"])
    assert by_un is not None
    assert by_un["id"] == u["id"]


def test_sa_create_user_account_and_get_global(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("AccT")
    row = s.create_user_account(
        tenant_id=t["id"],
        username="acctester",
        display_name="Acc",
        role="member",
        password_hash="h",
        is_active=True,
    )
    assert row.get("username") == "acctester"
    g = s.get_user_by_username_global(username="acctester")
    assert g is not None
    assert g["tenant_id"] == t["id"]


def test_sa_list_users_filter_order_and_flags(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("LU")
    u1 = s.create_user(tenant_id=t["id"], display_name="Alpha User", role="member")
    u2 = s.create_user(tenant_id=t["id"], display_name="Beta", role="owner")
    rows = s.list_users(tenant_id=t["id"], limit=10, offset=0)
    assert {u1["id"], u2["id"]}.issubset({r["id"] for r in rows})
    assert rows[0]["id"] == u2["id"]

    filtered = s.list_users(tenant_id=t["id"], q="alpha")
    assert len(filtered) == 1
    assert filtered[0]["id"] == u1["id"]


def test_sa_list_users_include_inactive(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("IA")
    s.create_user(tenant_id=t["id"], display_name="Active", role="member")
    inac = s.create_user_account(
        tenant_id=t["id"],
        username="inac1",
        display_name="Inactive",
        role="member",
        password_hash="x",
        is_active=False,
    )
    assert any(r["id"] == inac["id"] for r in s.list_users(tenant_id=t["id"], include_inactive=True))
    assert not any(r["id"] == inac["id"] for r in s.list_users(tenant_id=t["id"], include_inactive=False))


def test_sa_list_users_wecom_ids_and_update_delete(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("WC")
    u = s.create_user(tenant_id=t["id"], display_name="We", role="member")
    ts = "2026-01-01T00:00:00Z"
    with s._connect() as conn:
        conn.execute(
            """
            INSERT INTO channel_identity (tenant_id, channel, external_user_id, user_id, created_at)
            VALUES (?, 'wecom', 'ext-a', ?, ?)
            """,
            (t["id"], u["id"], ts),
        )
        conn.execute(
            """
            INSERT INTO channel_identity (tenant_id, channel, external_user_id, user_id, created_at)
            VALUES (?, 'wecom', 'ext-b', ?, ?)
            """,
            (t["id"], u["id"], ts),
        )
    row = next(r for r in s.list_users(tenant_id=t["id"]) if r["id"] == u["id"])
    assert row["wecom_linked"] is True
    assert row["channel_linked"] is True
    eids = row["wecom_external_user_ids"]
    assert "ext-a" in eids and "ext-b" in eids

    assert s.update_user_account(tenant_id=t["id"], user_id=u["id"], display_name="We2", role="owner") is True
    ref = s.get_user_by_id(tenant_id=t["id"], user_id=u["id"])
    assert ref is not None
    assert ref["display_name"] == "We2" and ref["role"] == "owner"

    assert s.delete_user_account(tenant_id=t["id"], user_id=u["id"]) == 1
    assert s.get_user_by_id(tenant_id=t["id"], user_id=u["id"]) is None


def test_sa_update_user_account_noop(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("NP")
    u = s.create_user(tenant_id=t["id"], display_name="N", role="member")
    assert s.update_user_account(tenant_id=t["id"], user_id=u["id"]) is False
