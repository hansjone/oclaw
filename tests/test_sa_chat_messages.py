"""SQLAlchemy slice tests: chat_message hot paths (phase-4 migration)."""

from __future__ import annotations

import json

import pytest

from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "sa_msg.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def test_sa_chat_message_add_list_meta(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("M")
    m1 = s.add_message(sess.id, "user", "hello")
    assert m1.id > 0
    m2 = s.add_message(sess.id, "assistant", "hi")
    assert m2.id > m1.id
    meta = s.get_session_messages_meta(sess.id)
    assert meta.session_id == sess.id
    assert meta.message_count == 2
    assert meta.last_message_id == m2.id
    assert s.count_messages(sess.id) == 2
    assert s.get_last_message_id(sess.id) == m2.id
    rows = s.get_messages(sess.id, limit=10)
    assert [x.role for x in rows] == ["user", "assistant"]
    assert rows[0].content == "hello"
    after = s.get_messages_after_id(session_id=sess.id, after_id=m1.id, limit=10)
    assert len(after) == 1
    assert after[0].id == m2.id


def test_sa_chat_message_delete_refreshes_session_ts(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("D")
    a = s.add_message(sess.id, "user", "a", timestamp="2020-01-01T00:00:01+00:00")
    b = s.add_message(sess.id, "user", "b", timestamp="2020-01-01T00:00:02+00:00")
    assert s.get_session(sess.id).last_message_at is not None
    assert s.delete_message(session_id=sess.id, message_id=b.id) is True
    meta = s.get_session_messages_meta(sess.id)
    assert meta.message_count == 1
    assert meta.last_message_id == a.id
    assert s.delete_message(session_id=sess.id, message_id=999999) is False


def test_sa_chat_message_update_content(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("U")
    m = s.add_message(sess.id, "assistant", "old", event_payload={"k": 1})
    ok = s.update_message_content(session_id=sess.id, message_id=m.id, content="new", event_payload={"k": 2})
    assert ok is True
    row = s.get_messages(sess.id, limit=5)[0]
    assert row.content == "new"
    assert json.loads(row.event_payload or "{}")["k"] == 2


def test_sa_chat_message_scrubs_nul_byte(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("N")
    m = s.add_message(sess.id, "user", "a\x00b", event_payload={"x": "y\x00z"})
    rows = s.get_messages(sess.id, limit=5)
    assert rows[0].content == "ab"
    ep = json.loads(rows[0].event_payload or "{}")
    assert ep["x"] == "yz"


def test_sa_chat_message_tool_window_prepend(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("T")
    asst = s.add_message(sess.id, "assistant", "call", tool_calls='{"x":1}')
    tool_calls = json.dumps({"assistant_message_id": asst.id}, ensure_ascii=False)
    s.add_message(sess.id, "tool", "result", tool_calls=tool_calls)
    win = s.get_messages(sess.id, limit=1)
    assert len(win) == 2
    assert win[0].id == asst.id
    assert win[1].role == "tool"
