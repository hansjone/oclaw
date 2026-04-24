from __future__ import annotations

import json
from pathlib import Path

from oclaw.runtime.chat.tool_runtime import ToolExecutionContext, ToolExecutor
from oclaw.platform.llm.chat_models import LLMToolCall
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.tools.base import ToolRegistry, ToolSpec


def test_tool_loop_guard_blocks_repeated_signature(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "g.sqlite"))
    sess = store.create_session("t")
    calls = {"n": 0}

    def _handler(args):
        calls["n"] += 1
        return {"ok": True, "echo": args}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="echo",
                description="echo",
                parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [
        LLMToolCall(id="c1", name="echo", arguments={"x": 1}),
        LLMToolCall(id="c2", name="echo", arguments={"x": 1}),
        LLMToolCall(id="c3", name="echo", arguments={"x": 1}),
    ]
    _, results = ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id),
        assistant_msg_id=1,
        tool_uses=tool_uses,
        signature_budget=2,
    )
    assert calls["n"] == 2
    blocked, _ = results["c3"]
    assert blocked.get("error_code") == "tool_loop_guard"


def test_repeated_tool_results_are_compacted_in_history(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "g2.sqlite"))
    sess = store.create_session("t")

    def _handler(_args):
        # Emulate large-ish tabular payload that should not be replayed verbatim repeatedly.
        return {"ok": True, "rows": [{"i": i, "v": f"row-{i}"} for i in range(0, 200)], "rows_returned": 200}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="run_tabular_sql",
                description="fetch rows",
                parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [
        LLMToolCall(id="c1", name="run_tabular_sql", arguments={"x": 1}),
        LLMToolCall(id="c2", name="run_tabular_sql", arguments={"x": 2}),
        LLMToolCall(id="c3", name="run_tabular_sql", arguments={"x": 3}),
    ]
    ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id, turn_uuid="turn-1"),
        assistant_msg_id=1,
        tool_uses=tool_uses,
    )
    rows = store.get_messages(session_id=sess.id, limit=50)
    tool_rows = [m for m in rows if str(getattr(m, "role", "") or "") == "tool"]
    assert len(tool_rows) == 3
    payloads = [json.loads(str(getattr(m, "content", "") or "{}")) for m in tool_rows]
    assert bool(payloads[0].get("_history_compacted"))
    assert bool(payloads[1].get("_history_compacted"))
    assert bool(payloads[2].get("_history_compacted"))
    assert str(payloads[2].get("_history_compact_reason") or "") == "repeated_tool_calls_in_turn"
    assert int(payloads[0].get("_tool_observed_rows_cumulative_in_turn") or 0) == 200
    assert int(payloads[1].get("_tool_observed_rows_cumulative_in_turn") or 0) == 400
    assert int(payloads[2].get("_tool_observed_rows_this_call") or 0) == 200
    assert int(payloads[2].get("_tool_observed_rows_cumulative_in_turn") or 0) == 600
    assert "audit_note" in payloads[2]


def test_repeated_non_sql_tools_are_not_compacted(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "g3.sqlite"))
    sess = store.create_session("t")

    def _handler(_args):
        return {"ok": True, "rows": [{"i": i} for i in range(0, 50)], "rows_returned": 50}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="generic_fetch",
                description="generic",
                parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [
        LLMToolCall(id="c1", name="generic_fetch", arguments={"x": 1}),
        LLMToolCall(id="c2", name="generic_fetch", arguments={"x": 2}),
        LLMToolCall(id="c3", name="generic_fetch", arguments={"x": 3}),
    ]
    ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id, turn_uuid="turn-2"),
        assistant_msg_id=1,
        tool_uses=tool_uses,
    )
    rows = store.get_messages(session_id=sess.id, limit=50)
    tool_rows = [m for m in rows if str(getattr(m, "role", "") or "") == "tool"]
    payloads = [json.loads(str(getattr(m, "content", "") or "{}")) for m in tool_rows]
    assert payloads
    assert not any(bool(p.get("_history_compacted")) for p in payloads)

