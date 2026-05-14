"""SQLAlchemy slice tests: chat_session list + CRUD (phase-3 migration)."""

from __future__ import annotations

import pytest

from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "sa_chat.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def test_sa_chat_session_crud(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    meta0 = s.get_sessions_list_meta()
    assert meta0.session_count == 0
    sess = s.create_session("Hi")
    assert s.get_session(sess.id) is not None
    assert s.get_session(sess.id).title == "Hi"
    assert s.count_sessions() == 1
    s.rename_session(sess.id, "Hi2")
    assert s.get_session(sess.id).title == "Hi2"
    listed = s.list_sessions(limit=5, offset=0)
    assert len(listed) == 1
    s.delete_session(sess.id)
    assert s.get_session(sess.id) is None


def test_sa_chat_session_user_scoped(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("ChatT")
    u = s.create_user(tenant_id=t["id"], display_name="ChatU", role="member")
    sess = s.create_session_for_user(title="Owned", tenant_id=t["id"], user_id=u["id"])
    rows = s.list_sessions_for_user(tenant_id=t["id"], user_id=u["id"], limit=10, offset=0)
    assert len(rows) == 1
    assert rows[0].id == sess.id
    assert s.get_session_for_user(session_id=sess.id, tenant_id=t["id"], user_id=u["id"]) is not None
    assert s.get_session_in_tenant(session_id=sess.id, tenant_id=t["id"]) is not None
    assert s.delete_session_for_user(session_id=sess.id, tenant_id=t["id"], user_id=u["id"]) is True
    assert s.get_session(sess.id) is None
