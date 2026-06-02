from __future__ import annotations

import hashlib

import pytest

from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore
from svc.persistence.assistant_store import reset_assistant_store_singleton


@pytest.fixture
def store_two_tenants(monkeypatch: pytest.MonkeyPatch, tmp_path) -> SqliteStore:
    monkeypatch.delenv("AIA_ASSISTANT_DATABASE_URL", raising=False)
    monkeypatch.setenv("AIA_ASSISTANT_DB_BACKEND", "sqlite")
    dbfile = tmp_path / "admin_xtenant.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    reset_assistant_store_singleton()
    s = SqliteStore(str(dbfile))
    pwd_hash = hashlib.sha256(b"pass").hexdigest()
    t1 = s.create_tenant("Team")
    t2 = s.create_tenant("Other")
    u1 = s.create_user_account(
        tenant_id=str(t1["id"]),
        username="administrator",
        display_name="Admin",
        role="admin",
        password_hash=pwd_hash,
        is_active=True,
    )
    s.create_user_account(
        tenant_id=str(t2["id"]),
        username="administrator",
        display_name="Admin",
        role="admin",
        password_hash=pwd_hash,
        is_active=True,
    )
    s.create_session_for_user(title="team-sess", tenant_id=str(t1["id"]), user_id=str(u1["id"]))
    s.create_session_for_user(
        title="other-sess",
        tenant_id=str(t2["id"]),
        user_id=str(s.get_user_by_username(tenant_id=str(t2["id"]), username="administrator")["id"]),
    )
    yield s
    clear_assistant_engine_cache()
    reset_assistant_store_singleton()


def test_list_sessions_for_administrator_username_cross_tenant(
    store_two_tenants: SqliteStore,
) -> None:
    s = store_two_tenants
    rows = s.list_sessions_for_administrator_username(username="administrator", limit=50)
    titles = {x.title for x in rows}
    assert "team-sess" in titles
    assert "other-sess" in titles
    meta = s.get_sessions_list_meta_for_administrator_username(username="administrator")
    assert int(meta.session_count or 0) == 2


def test_delete_session_for_administrator_username_cross_tenant(
    store_two_tenants: SqliteStore,
) -> None:
    s = store_two_tenants
    rows = s.list_sessions_for_administrator_username(username="administrator", limit=50)
    other = next(x for x in rows if x.title == "other-sess")
    team = next(x for x in rows if x.title == "team-sess")
    team_owner = s.get_ui_session_owner(session_id=str(team.id))
    login_tid = str((team_owner or {}).get("tenant_id") or "")
    assert login_tid
    assert s.delete_session_in_tenant(session_id=str(other.id), tenant_id=login_tid) is False
    assert s.get_session_for_administrator_username(session_id=str(other.id), username="administrator") is not None
    assert s.delete_session_for_administrator_username(session_id=str(other.id), username="administrator") is True
    assert s.get_session_for_administrator_username(session_id=str(other.id), username="administrator") is None
    meta = s.get_sessions_list_meta_for_administrator_username(username="administrator")
    assert int(meta.session_count or 0) == 1
