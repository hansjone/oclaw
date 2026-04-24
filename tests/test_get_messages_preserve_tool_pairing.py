from __future__ import annotations

import json
from pathlib import Path

from oclaw.runtime.chat.agent_messages import build_llm_messages
from oclaw.platform.llm.chat_models import RuleBasedChatModel
from oclaw.platform.persistence.sqlite_store import SqliteStore


def test_get_messages_limit_preserves_tool_pairing(tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite"
    store = SqliteStore(str(db))
    sess = store.create_session("t")

    store.add_message(session_id=sess.id, role="user", content="hi", turn_uuid="turn-1", event_type="user_text")
    assistant = store.add_message(
        session_id=sess.id,
        role="assistant",
        content="",
        turn_uuid="turn-1",
        event_type="tool_call",
        tool_calls=[
            {
                "id": "call_abc",
                "name": "mcp__x__list_directory",
                "arguments": {"path": "C:\\dummy"},
            }
        ],
    )
    # Tool result must keep tool_call_id + assistant_message_id for pairing.
    store.add_message(
        session_id=sess.id,
        role="tool",
        content=json.dumps({"ok": False, "error": "Access denied", "result": {"isError": True}}, ensure_ascii=False),
        turn_uuid="turn-1",
        event_type="tool_result",
        tool_calls={"tool_call_id": "call_abc", "name": "mcp__x__list_directory", "assistant_message_id": int(assistant.id)},
    )

    # Boundary case: only ask for the last 1 message. Store must prepend the assistant row to keep pairing.
    rows = store.get_messages(session_id=sess.id, limit=1)
    assert len(rows) >= 2
    assert rows[-1].role == "tool"
    assert any(r.role == "assistant" and r.tool_calls for r in rows)
    assert all(str(getattr(r, "turn_uuid", "") or "") == "turn-1" for r in rows)

    msgs = build_llm_messages(store_messages=rows, system_prompt="s", model=RuleBasedChatModel(), lang="zh")
    tool_msgs = [m for m in msgs if m.get("role") == "tool"]
    assert tool_msgs, msgs
    assert tool_msgs[-1].get("tool_call_id") == "call_abc"

