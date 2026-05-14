"""SA migration: tool_log MCP queries + trace_event writes/lists."""

from __future__ import annotations

import pytest

from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "sa_tl_tr.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def test_sa_mcp_tool_summaries_and_call_logs(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("MCP2")
    s.add_tool_log(sess.id, "mcp__srv99__x", {}, {"ok": True}, specialist="sp1")
    s.add_tool_log(sess.id, "mcp__srv99__x", {}, {"ok": True}, specialist="sp1")
    agg = s.list_mcp_tool_aggregate_usage()
    assert "mcp__srv99__x" in agg
    assert agg["mcp__srv99__x"]["count"] == 2
    summ = s.list_mcp_tool_usage_summary(limit=50)
    hit = next(x for x in summ if x["tool_name"] == "mcp__srv99__x")
    assert hit["count"] == 2
    assert hit["server_id"] == "srv99"
    logs = s.list_mcp_tool_call_logs(server_id="srv99", limit=10)
    assert len(logs) == 2
    assert logs[0]["session_id"] == sess.id


def test_sa_trace_roundtrip_batch_and_window(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("TR")
    s.add_trace_event(
        session_id=sess.id,
        trace_id="t1",
        span_id="s0",
        parent_span_id=None,
        event_type="noise",
        payload={"a": 1},
    )
    s.add_trace_events_batch(
        [
            {
                "session_id": sess.id,
                "trace_id": "t1",
                "span_id": "s1",
                "parent_span_id": None,
                "event_type": "turn_started",
                "payload": {},
            },
            {
                "session_id": sess.id,
                "trace_id": "t1",
                "span_id": "s2",
                "parent_span_id": None,
                "event_type": "turn_finished",
                "payload": {},
            },
        ]
    )
    desc = s.list_trace_events(session_id=sess.id, limit=10)
    assert len(desc) == 3
    asc_rows = s.list_trace_events_for_trace(session_id=sess.id, trace_id="t1", limit=50)
    assert len(asc_rows) == 3
    assert asc_rows[0]["event_type"] == "noise"
    st, en = s.get_turn_time_window(session_id=sess.id, trace_id="t1")
    assert st is not None and en is not None


def test_sa_add_tool_log_get_tool_logs(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("TL")
    s.add_tool_log(sess.id, "my_tool", {"a": 1}, {"ok": True}, specialist="spec", duration_ms=42)
    logs = s.get_tool_logs(sess.id, limit=10)
    assert len(logs) == 1
    assert logs[0]["tool_name"] == "my_tool"
    assert logs[0]["specialist"] == "spec"
    assert logs[0]["args"] == {"a": 1}
    assert logs[0]["result"] == {"ok": True}
    assert logs[0]["duration_ms"] == 42


def test_sa_list_messages_in_time_window(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("Win")
    t0 = "2024-01-01T10:00:00+00:00"
    t1 = "2024-01-01T10:05:00+00:00"
    t2 = "2024-01-01T10:10:00+00:00"
    s.add_message(sess.id, "user", "a", timestamp=t0)
    s.add_message(sess.id, "user", "b", timestamp=t1)
    s.add_message(sess.id, "user", "c", timestamp=t2)
    rows = s.list_messages_in_time_window(session_id=sess.id, start_ts=t0, end_ts=t1, limit=50)
    assert len(rows) == 2
    assert [x["content"] for x in rows] == ["a", "b"]


def test_sa_move_tool_logs_to_session(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    src = s.create_session("SrcS")
    dst = s.create_session("DstS")
    s.add_tool_log(src.id, "t_move", {}, {"ok": 1})
    n = s.move_tool_logs_to_session(from_session_id=src.id, to_session_id=dst.id)
    assert n == 1
    assert s.get_tool_logs(src.id, limit=10) == []
    logs = s.get_tool_logs(dst.id, limit=10)
    assert len(logs) == 1
    assert logs[0]["tool_name"] == "t_move"
    assert s.move_tool_logs_to_session(from_session_id=src.id, to_session_id=dst.id) == 0
    assert s.move_tool_logs_to_session(from_session_id="", to_session_id=dst.id) == 0
