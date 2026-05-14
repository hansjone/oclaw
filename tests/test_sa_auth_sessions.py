"""SQLAlchemy slice tests: auth_session repository (phase-2 migration)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest

from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "sa_auth.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def _future_expires() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()


def test_sa_auth_session_roundtrip(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("AuthSlice")
    u = s.create_user(tenant_id=t["id"], display_name="Member", role="member")
    h = "tokhash_" + uuid.uuid4().hex
    exp = _future_expires()
    s.create_auth_session(
        session_token_hash=h,
        tenant_id=t["id"],
        user_id=u["id"],
        role="member",
        expires_at=exp,
    )
    row = s.get_auth_session(session_token_hash=h)
    assert row is not None
    assert row["tenant_id"] == t["id"]
    assert row["user_id"] == u["id"]
    assert not row.get("revoked_at")
    s.touch_auth_session(session_token_hash=h)
    row2 = s.get_auth_session(session_token_hash=h)
    assert row2 is not None
    assert row2["last_seen_at"] is not None
    assert s.revoke_auth_session(session_token_hash=h) == 1
    assert s.revoke_auth_session(session_token_hash=h) == 0
    row3 = s.get_auth_session(session_token_hash=h)
    assert row3 is not None
    assert row3.get("revoked_at")


def test_sa_auth_session_revoke_all(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("AuthSlice2")
    u = s.create_user(tenant_id=t["id"], display_name="M2", role="member")
    exp = _future_expires()
    for i in range(2):
        s.create_auth_session(
            session_token_hash=f"h{i}_" + uuid.uuid4().hex,
            tenant_id=t["id"],
            user_id=u["id"],
            role="member",
            expires_at=exp,
        )
    n = s.revoke_all_auth_sessions()
    assert n == 2
