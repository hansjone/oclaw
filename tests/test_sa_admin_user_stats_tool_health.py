"""SA migration: list_admin_user_stats + list_session_tool_health."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "sa_admin_th.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def test_sa_list_admin_user_stats_tokens_sessions_logins(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("StatsT")
    u = s.create_user(tenant_id=t["id"], display_name="Stats User", role="member")
    sess = s.create_session_for_user(title="Sess", tenant_id=t["id"], user_id=u["id"])
    s.add_message(sess.id, "user", "hi")
    s.add_trace_event(
        session_id=sess.id,
        trace_id="tr1",
        span_id="sp1",
        parent_span_id=None,
        event_type="llm",
        payload={"prompt_tokens_est": 12, "response_tokens_est": 3},
    )
    exp = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    s.create_auth_session(
        session_token_hash="tok_stats_" + sess.id[:8],
        tenant_id=t["id"],
        user_id=u["id"],
        role="member",
        expires_at=exp,
    )
    total, users, totals = s.list_admin_user_stats(tenant_id=t["id"], limit=50, offset=0)
    assert total >= 1
    row = next(x for x in users if x["user_id"] == u["id"])
    assert row["sessions_count"] >= 1
    assert row["total_tokens_est"] == 15
    assert totals["users_count"] == total
    assert totals["active_sessions_30m"] >= 1
    assert totals["active_logins_30m"] >= 1


def test_sa_list_session_tool_health_warn_then_ok(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("TH")
    s.add_message(sess.id, "assistant", "only assistant")
    rows = s.list_session_tool_health(session_id=sess.id, limit=10)
    assert len(rows) == 1
    assert rows[0]["status"] == "warn_no_tool_calls"
    assert rows[0]["assistant_count"] == 1
    s.add_tool_log(sess.id, "grep", {}, {"ok": True})
    rows2 = s.list_session_tool_health(session_id=sess.id, limit=10)
    assert rows2[0]["status"] == "ok"
    assert rows2[0]["tool_count"] >= 1


def test_sa_list_session_tool_health_mcp_count(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("MCP")
    s.add_tool_log(sess.id, "mcp__srv1__ping", {}, {"ok": True})
    rows = s.list_session_tool_health(session_id=sess.id, limit=10)
    assert rows[0]["mcp_tool_count"] == 1
