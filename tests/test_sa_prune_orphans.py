"""SA housekeeping: delete orphan chat_message / tool_log rows."""

from __future__ import annotations

import pytest

from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "sa_prune.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def test_sa_delete_orphan_chat_message_and_tool_log(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    with s._connect() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "INSERT INTO chat_message (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            ("ghost-sid", "user", "orphan", "2020-01-01T00:00:00+00:00"),
        )
        conn.execute(
            """
            INSERT INTO tool_log (session_id, tool_name, specialist, args, result, timestamp, duration_ms)
            VALUES (?, ?, '', '{}', '{}', ?, NULL)
            """,
            ("ghost-sid", "t", "2020-01-01T00:00:01+00:00"),
        )
        conn.execute("PRAGMA foreign_keys = ON")
    n_msg = s._chat_messages_repo().delete_messages_where_session_missing()
    n_tl = s._tool_log_queries_repo().delete_tool_logs_where_session_missing()
    assert n_msg >= 1
    assert n_tl >= 1


def test_sa_prune_runs_with_sa_deletes(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    s.create_session("keep")
    with s._connect() as conn:
        s._prune_rows_for_missing_chat_session(conn)
    # second call should not raise
    with s._connect() as conn:
        s._prune_rows_for_missing_chat_session(conn)
