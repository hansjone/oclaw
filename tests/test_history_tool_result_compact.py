from __future__ import annotations

import json

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.chat.history_tool_result_compact import compact_tool_results_in_session_history


def test_compact_tool_results_in_session_history_rewrites_large_tool_message(tmp_path) -> None:  # noqa: ANN001
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    sess = store.create_session("t")
    store.add_message(session_id=sess.id, role="user", content="hi", event_type="user_text")
    big = {"ok": True, "data": "x" * 10000}
    store.add_message(session_id=sess.id, role="tool", content=json.dumps(big), event_type="tool_result")

    out = compact_tool_results_in_session_history(store=store, session_id=sess.id, cap_chars=8000, limit_messages=200)
    assert out.ok is True
    assert out.compacted_tool_messages == 1
    assert out.rewritten_all_tool_messages >= 0

    msgs = store.get_messages(session_id=sess.id, limit=50)
    tool = next((m for m in msgs if str(getattr(m, "role", "")) == "tool"), None)
    assert tool is not None
    txt = str(getattr(tool, "content", "") or "")
    obj = json.loads(txt)
    assert obj.get("_tool_result_guarded") is True
    assert int(obj.get("guard_cap_chars") or 0) == 8000


def test_compact_tool_results_rewrite_all_small_rows(tmp_path) -> None:  # noqa: ANN001
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    sess = store.create_session("t2")
    store.add_message(session_id=sess.id, role="tool", content=json.dumps({"ok": True, "value": "small"}), event_type="tool_result")

    out = compact_tool_results_in_session_history(store=store, session_id=sess.id, cap_chars=8000, limit_messages=200, rewrite_all=True)
    assert out.ok is True
    assert out.rewritten_all_tool_messages >= 1
    msgs = store.get_messages(session_id=sess.id, limit=10)
    tool = next((m for m in msgs if str(getattr(m, "role", "")) == "tool"), None)
    assert tool is not None
    obj = json.loads(str(getattr(tool, "content", "") or "{}"))
    assert obj.get("_history_full_rewrite") is True

