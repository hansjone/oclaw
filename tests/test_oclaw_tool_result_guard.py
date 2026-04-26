from __future__ import annotations

from pathlib import Path

from oclaw.runtime.direct_loop import _OCLAW_TOOL_RESULT_HARD_CAP_CHARS, _build_model_context
from oclaw.platform.llm.chat_models import RuleBasedChatModel
from oclaw.platform.persistence.sqlite_store import SqliteStore


def test_oclaw_tool_result_context_guard_truncates_large_tool_message(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    sess = store.create_session("t")
    # Ensure the tool message is not a dangling orphan (some providers require pairing).
    store.add_message(
        session_id=sess.id,
        role="assistant",
        content="",
        tool_calls=[{"id": "c1", "name": "echo", "arguments": {"x": 1}}],
    )
    huge = "X" * (_OCLAW_TOOL_RESULT_HARD_CAP_CHARS + 5000)
    store.add_message(
        session_id=sess.id,
        role="tool",
        content='{"ok": true, "blob": "' + huge + '"}',
        tool_calls={"tool_call_id": "c1", "name": "echo", "assistant_message_id": 1},
    )
    msgs = _build_model_context(
        store=store,
        session_id=sess.id,
        max_messages=50,
        system_prompt="sys",
        model=RuleBasedChatModel(),
        lang="zh",
        memory_context=None,
        trace_id="t1",
        parent_span_id=None,
    )
    tool_msgs = [m for m in msgs if m.get("role") == "tool"]
    assert tool_msgs, msgs
    guarded = str(tool_msgs[-1].get("content") or "")
    assert len(guarded) <= _OCLAW_TOOL_RESULT_HARD_CAP_CHARS + 2000
    assert "_tool_result_guarded" in guarded


def test_oclaw_tool_result_context_guard_skips_active_turn_tool_messages(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    sess = store.create_session("t")
    turn_uuid = "turn-active-1"
    store.add_message(
        session_id=sess.id,
        role="assistant",
        content="",
        tool_calls=[{"id": "c1", "name": "echo", "arguments": {"x": 1}}],
        turn_uuid=turn_uuid,
    )
    huge = "X" * (_OCLAW_TOOL_RESULT_HARD_CAP_CHARS + 5000)
    store.add_message(
        session_id=sess.id,
        role="tool",
        content='{"ok": true, "blob": "' + huge + '"}',
        tool_calls={"tool_call_id": "c1", "name": "echo", "assistant_message_id": 1},
        turn_uuid=turn_uuid,
    )
    msgs = _build_model_context(
        store=store,
        session_id=sess.id,
        max_messages=50,
        system_prompt="sys",
        model=RuleBasedChatModel(),
        lang="zh",
        memory_context=None,
        trace_id="t1",
        parent_span_id=None,
        active_turn_uuid=turn_uuid,
    )
    tool_msgs = [m for m in msgs if m.get("role") == "tool"]
    assert tool_msgs, msgs
    raw = str(tool_msgs[-1].get("content") or "")
    assert "_tool_result_guarded" not in raw

