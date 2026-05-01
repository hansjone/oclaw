from __future__ import annotations

from oclaw.platform.persistence.sqlite_store import SqliteStore


def test_delete_session_cascades_chat_message_and_tool_log(tmp_path) -> None:  # noqa: ANN001
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    sess = store.create_session("t")
    store.add_message(session_id=sess.id, role="user", content="hi", event_type="user_text")
    store.add_tool_log(session_id=sess.id, tool_name="x", args={"a": 1}, result={"ok": True})

    store.delete_session(sess.id)

    with store._connect() as conn:  # noqa: SLF001
        c1 = conn.execute("select count(1) from chat_message where session_id=?", (sess.id,)).fetchone()[0]
        c2 = conn.execute("select count(1) from tool_log where session_id=?", (sess.id,)).fetchone()[0]
        c3 = conn.execute("select count(1) from chat_session where id=?", (sess.id,)).fetchone()[0]
    assert int(c3) == 0
    assert int(c1) == 0
    assert int(c2) == 0

