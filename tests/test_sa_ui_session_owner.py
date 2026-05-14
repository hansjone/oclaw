"""SA migration: ui_session_owner upsert + backfill."""

from __future__ import annotations

import pytest

from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "sa_ui_owner.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def test_sa_create_session_for_user_and_get_owner(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("UIO")
    u = s.create_user(tenant_id=t["id"], display_name="U", role="member")
    sess = s.create_session_for_user(title="T", tenant_id=t["id"], user_id=u["id"])
    row = s.get_ui_session_owner(session_id=sess.id)
    assert row is not None
    assert row["tenant_id"] == t["id"]
    assert row["user_id"] == u["id"]
    s.ensure_ui_session_owner(session_id=sess.id, tenant_id=t["id"], user_id=u["id"])
    row2 = s.get_ui_session_owner(session_id=sess.id)
    assert row2 == row


def test_sa_upsert_replace_changes_owner(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("UIO2")
    u1 = s.create_user(tenant_id=t["id"], display_name="A", role="member")
    u2 = s.create_user(tenant_id=t["id"], display_name="B", role="member")
    sess = s.create_session_for_user(title="X", tenant_id=t["id"], user_id=u1["id"])
    s._ui_session_owner_repo().upsert_replace(
        session_id=sess.id,
        tenant_id=t["id"],
        user_id=u2["id"],
        created_at="2099-01-01T00:00:00+00:00",
    )
    row = s.get_ui_session_owner(session_id=sess.id)
    assert row is not None
    assert row["user_id"] == u2["id"]


def test_sa_backfill_orphan_sessions(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("BF")
    u = s.create_user(tenant_id=t["id"], display_name="BFU", role="member")
    orphan = s.create_session("orphan title")
    assert s.get_ui_session_owner(session_id=orphan.id) is None
    n = s.backfill_orphan_chat_sessions_for_user(tenant_id=t["id"], user_id=u["id"])
    assert n >= 1
    row = s.get_ui_session_owner(session_id=orphan.id)
    assert row is not None
    assert row["user_id"] == u["id"]


def test_sa_backfill_ui_session_owner_from_channel_v2(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("CH")
    u = s.create_user(tenant_id=t["id"], display_name="CHU", role="member")
    sess = s.create_session("ch sess")
    ts = "2025-01-01T00:00:00+00:00"
    with s._connect() as conn:
        conn.execute(
            """
            INSERT INTO channel_identity_v2
                (tenant_id, channel, account_id, external_user_id, user_id, created_at)
            VALUES (?, 'wecom', 'acc1', 'extu', ?, ?)
            """,
            (t["id"], u["id"], ts),
        )
        conn.execute(
            """
            INSERT INTO channel_session_v2
                (tenant_id, channel, account_id, external_chat_id, external_user_id, session_id, created_at)
            VALUES (?, 'wecom', 'acc1', 'chat1', 'extu', ?, ?)
            """,
            (t["id"], sess.id, ts),
        )
    n = s.backfill_ui_session_owner_from_channel_v2()
    assert n >= 1
    row = s.get_ui_session_owner(session_id=sess.id)
    assert row is not None
    assert row["user_id"] == u["id"]
