"""SA migration: fork_session, trim_messages, list_admin_sessions."""

from __future__ import annotations

import json

import pytest

from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "sa_fork.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def test_sa_fork_session_remaps_tool_assistant_id(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    src = s.create_session("Src")
    asst = s.add_message(src.id, "assistant", "a", tool_calls="{}")
    tc = json.dumps({"assistant_message_id": asst.id}, ensure_ascii=False)
    s.add_message(src.id, "tool", "t", tool_calls=tc)
    forked = s.fork_session(src.id, up_to_message_id=int(asst.id) + 1, title="Forked")
    assert forked.id != src.id
    msgs = s.get_messages(forked.id, limit=10)
    assert len(msgs) == 2
    assert msgs[0].role == "assistant"
    assert msgs[1].role == "tool"
    meta = json.loads(msgs[1].tool_calls or "{}")
    assert int(meta.get("assistant_message_id") or 0) == msgs[0].id


def test_sa_fork_session_bad_anchor(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    src = s.create_session("S2")
    m = s.add_message(src.id, "user", "x")
    n_before = s.count_sessions()
    with pytest.raises(ValueError, match="message not in session"):
        s.fork_session(src.id, up_to_message_id=int(m.id) + 99, title="Bad")
    assert s.count_sessions() == n_before


def test_sa_trim_messages_keep_last(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("Trim")
    for i in range(5):
        s.add_message(sess.id, "user", f"m{i}")
    s.trim_messages(sess.id, keep_last=2)
    assert s.count_messages(sess.id) == 2
    rows = s.get_messages(sess.id, limit=10)
    assert [x.content for x in rows] == ["m3", "m4"]


def test_sa_trim_messages_zero_deletes_session(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    sess = s.create_session("Z")
    s.add_message(sess.id, "user", "u")
    s.trim_messages(sess.id, keep_last=0)
    assert s.get_session(sess.id) is None


def test_sa_list_admin_sessions(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    t = s.create_tenant("AdmT")
    u = s.create_user(tenant_id=t["id"], display_name="Alice Admin", role="member")
    sess = s.create_session_for_user(title="S1", tenant_id=t["id"], user_id=u["id"])
    s.add_message(sess.id, "user", "hello")
    total, rows = s.list_admin_sessions(tenant_id=t["id"], limit=10, offset=0)
    assert total >= 1
    hit = next(x for x in rows if x["session_id"] == sess.id)
    assert hit["message_count"] == 1
    assert "alice" in hit["display_name"].lower() or "alice" in hit["username"].lower()
    t2, rows2 = s.list_admin_sessions(tenant_id=t["id"], q="S1", limit=10, offset=0)
    assert t2 >= 1
    assert any(x["session_id"] == sess.id for x in rows2)
