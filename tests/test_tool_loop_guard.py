from __future__ import annotations

import base64
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


def test_tool_result_image_blob_persisted_as_attachment_ref(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "img.sqlite"))
    sess = store.create_session("t")

    def _handler(_args):
        raw = base64.b64encode(b"\x89PNGtest-image").decode("ascii")
        return {
            "ok": True,
            "result": {"content": [{"type": "image", "mime": "image/png", "data": raw, "name": "mcp.png"}]},
        }

    reg = ToolRegistry(
        [
            ToolSpec(
                name="mcp_image_tool",
                description="returns image payload",
                parameters={"type": "object", "properties": {}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [LLMToolCall(id="c1", name="mcp_image_tool", arguments={})]
    ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id, turn_uuid="turn-img"),
        assistant_msg_id=1,
        tool_uses=tool_uses,
    )
    rows = store.get_messages(session_id=sess.id, limit=20)
    tool_rows = [m for m in rows if str(getattr(m, "role", "") or "") == "tool"]
    assert len(tool_rows) == 1
    payload = json.loads(str(getattr(tool_rows[0], "content", "") or "{}"))
    blk = (((payload.get("result") or {}).get("content") or [{}])[0]) if isinstance(payload, dict) else {}
    assert isinstance(blk, dict)
    assert str(blk.get("type") or "") == "image_ref"
    assert str(blk.get("attachment_id") or "")
    assert "data" not in blk
    atts = json.loads(str(getattr(tool_rows[0], "attachments", "") or "[]"))
    assert isinstance(atts, list) and atts
    assert str((atts[0] or {}).get("type") or "") == "image_ref"
    assert str((atts[0] or {}).get("attachment_id") or "")
    logs = store.get_tool_logs(sess.id, limit=10)
    assert logs and isinstance(logs[0], dict)
    body = logs[0].get("result") or {}
    blk2 = (((body.get("result") or {}).get("content") or [{}])[0]) if isinstance(body, dict) else {}
    assert isinstance(blk2, dict)
    assert str(blk2.get("type") or "") == "image_ref"
    assert "data" not in blk2


def test_tool_result_non_image_base64_persisted_as_binary_ref(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "bin.sqlite"))
    sess = store.create_session("t")

    def _handler(_args):
        raw = base64.b64encode(b"PK\x03\x04fake-zip-bytes").decode("ascii")
        return {"ok": True, "result": {"content": [{"type": "file", "mime": "application/zip", "base64": raw, "name": "a.zip"}]}}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="mcp_file_tool",
                description="returns file payload",
                parameters={"type": "object", "properties": {}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id, turn_uuid="turn-bin"),
        assistant_msg_id=1,
        tool_uses=[LLMToolCall(id="c1", name="mcp_file_tool", arguments={})],
    )
    rows = store.get_messages(session_id=sess.id, limit=20)
    tool_rows = [m for m in rows if str(getattr(m, "role", "") or "") == "tool"]
    assert len(tool_rows) == 1
    payload = json.loads(str(getattr(tool_rows[0], "content", "") or "{}"))
    blk = (((payload.get("result") or {}).get("content") or [{}])[0]) if isinstance(payload, dict) else {}
    assert isinstance(blk, dict)
    assert str(blk.get("type") or "") == "binary_ref"
    assert str(blk.get("attachment_id") or "")
    assert "base64" not in blk
    atts = json.loads(str(getattr(tool_rows[0], "attachments", "") or "[]"))
    assert isinstance(atts, list) and atts
    assert str((atts[0] or {}).get("type") or "") == "binary_ref"


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


def test_tabular_tools_blocked_without_tabular_ref(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "g4.sqlite"))
    sess = store.create_session("t")
    # A normal user turn without tabular_ref attachments.
    store.add_message(session_id=sess.id, role="user", content="analyze this file", attachments=[{"type": "text", "name": "x"}])

    def _handler(_args):
        return {"ok": True, "rows": []}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="query_tabular_attachment",
                description="query table",
                parameters={"type": "object", "properties": {"table_id": {"type": "string"}}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [LLMToolCall(id="c1", name="query_tabular_attachment", arguments={"table_id": "日志.xlsx"})]
    _, results = ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id),
        assistant_msg_id=1,
        tool_uses=tool_uses,
    )
    blocked, _ = results["c1"]
    assert not bool(blocked.get("ok"))
    assert str(blocked.get("error_code") or "") == "tabular_ref_missing"


def test_tabular_tools_allowed_with_tabular_ref(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "g5.sqlite"))
    sess = store.create_session("t")
    store.add_message(
        session_id=sess.id,
        role="user",
        content="uploaded table",
        attachments=[{"type": "tabular_ref", "table_id": "a" * 64, "name": "ok.xlsx"}],
    )
    calls = {"n": 0}

    def _handler(_args):
        calls["n"] += 1
        return {"ok": True, "rows": [{"x": 1}]}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="query_tabular_attachment",
                description="query table",
                parameters={"type": "object", "properties": {"table_id": {"type": "string"}}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [LLMToolCall(id="c1", name="query_tabular_attachment", arguments={"table_id": "a" * 64})]
    _, results = ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id),
        assistant_msg_id=1,
        tool_uses=tool_uses,
    )
    ok_res, _ = results["c1"]
    assert bool(ok_res.get("ok"))
    assert calls["n"] == 1


def test_text_tools_blocked_without_text_ref(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "g6.sqlite"))
    sess = store.create_session("t")
    store.add_message(session_id=sess.id, role="user", content="summarize", attachments=[{"type": "text", "name": "a.txt"}])

    def _handler(_args):
        return {"ok": True, "rows": []}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="query_text_attachment",
                description="query text",
                parameters={"type": "object", "properties": {"text_id": {"type": "string"}}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [LLMToolCall(id="c1", name="query_text_attachment", arguments={"text_id": "a" * 64})]
    _, results = ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id),
        assistant_msg_id=1,
        tool_uses=tool_uses,
    )
    blocked, _ = results["c1"]
    assert not bool(blocked.get("ok"))
    assert str(blocked.get("error_code") or "") == "text_ref_missing"


def test_text_tools_allowed_with_text_ref(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "g7.sqlite"))
    sess = store.create_session("t")
    store.add_message(
        session_id=sess.id,
        role="user",
        content="uploaded long text",
        attachments=[{"type": "text_ref", "text_id": "b" * 64, "name": "long.txt"}],
    )
    calls = {"n": 0}

    def _handler(_args):
        calls["n"] += 1
        return {"ok": True, "rows": [{"x": 1}]}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="query_text_attachment",
                description="query text",
                parameters={"type": "object", "properties": {"text_id": {"type": "string"}}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [LLMToolCall(id="c1", name="query_text_attachment", arguments={"text_id": "b" * 64})]
    _, results = ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id),
        assistant_msg_id=1,
        tool_uses=tool_uses,
    )
    ok_res, _ = results["c1"]
    assert bool(ok_res.get("ok"))
    assert calls["n"] == 1


def test_image_tools_blocked_without_image_ref(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "g8.sqlite"))
    sess = store.create_session("t")
    store.add_message(session_id=sess.id, role="user", content="analyze image", attachments=[{"type": "text", "name": "x"}])

    def _handler(_args):
        return {"ok": True}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="query_image_attachment",
                description="query image",
                parameters={"type": "object", "properties": {"attachment_id": {"type": "string"}}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [LLMToolCall(id="c1", name="query_image_attachment", arguments={"attachment_id": "abc"})]
    _, results = ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id),
        assistant_msg_id=1,
        tool_uses=tool_uses,
    )
    blocked, _ = results["c1"]
    assert not bool(blocked.get("ok"))
    assert str(blocked.get("error_code") or "") == "image_ref_missing"


def test_image_tools_allowed_with_image_ref(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "g9.sqlite"))
    sess = store.create_session("t")
    store.add_message(
        session_id=sess.id,
        role="user",
        content="uploaded image",
        attachments=[{"type": "image_ref", "attachment_id": "abc", "mime": "image/png"}],
    )
    calls = {"n": 0}

    def _handler(_args):
        calls["n"] += 1
        return {"ok": True}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="query_image_attachment",
                description="query image",
                parameters={"type": "object", "properties": {"attachment_id": {"type": "string"}}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [LLMToolCall(id="c1", name="query_image_attachment", arguments={"attachment_id": "abc"})]
    _, results = ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id),
        assistant_msg_id=1,
        tool_uses=tool_uses,
    )
    ok_res, _ = results["c1"]
    assert bool(ok_res.get("ok"))
    assert calls["n"] == 1


def test_video_tools_blocked_without_video_ref(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "g10.sqlite"))
    sess = store.create_session("t")
    store.add_message(session_id=sess.id, role="user", content="analyze video", attachments=[{"type": "text", "name": "x"}])

    def _handler(_args):
        return {"ok": True}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="query_video_attachment",
                description="query video",
                parameters={"type": "object", "properties": {"attachment_id": {"type": "string"}}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [LLMToolCall(id="c1", name="query_video_attachment", arguments={"attachment_id": "abc"})]
    _, results = ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id),
        assistant_msg_id=1,
        tool_uses=tool_uses,
    )
    blocked, _ = results["c1"]
    assert not bool(blocked.get("ok"))
    assert str(blocked.get("error_code") or "") == "video_ref_missing"


def test_video_tools_allowed_with_video_ref(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "g11.sqlite"))
    sess = store.create_session("t")
    store.add_message(
        session_id=sess.id,
        role="user",
        content="uploaded video",
        attachments=[{"type": "video_ref", "attachment_id": "abc", "mime": "video/mp4"}],
    )
    calls = {"n": 0}

    def _handler(_args):
        calls["n"] += 1
        return {"ok": True}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="query_video_attachment",
                description="query video",
                parameters={"type": "object", "properties": {"attachment_id": {"type": "string"}}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [LLMToolCall(id="c1", name="query_video_attachment", arguments={"attachment_id": "abc"})]
    _, results = ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id),
        assistant_msg_id=1,
        tool_uses=tool_uses,
    )
    ok_res, _ = results["c1"]
    assert bool(ok_res.get("ok"))
    assert calls["n"] == 1


def test_tool_result_image_payload_persisted_as_attachments(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "g12.sqlite"))
    sess = store.create_session("t")

    def _handler(_args):
        return {
            "ok": True,
            "result": {
                "content": [
                    {"type": "image", "data": "YWJj", "mime_type": "image/png"},
                    {"type": "image_url", "url": "https://example.com/a.png"},
                ]
            },
        }

    reg = ToolRegistry(
        [
            ToolSpec(
                name="make_image",
                description="make image",
                parameters={"type": "object", "properties": {}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    tool_uses = [LLMToolCall(id="c1", name="make_image", arguments={})]
    ToolExecutor().execute_tool_uses(
        ctx=ToolExecutionContext(store=store, tools=reg, session_id=sess.id),
        assistant_msg_id=1,
        tool_uses=tool_uses,
    )
    rows = store.get_messages(session_id=sess.id, limit=10)
    tool_rows = [m for m in rows if str(getattr(m, "role", "") or "") == "tool"]
    assert len(tool_rows) == 1
    attachments = json.loads(str(getattr(tool_rows[0], "attachments", "") or "[]"))
    assert any(str(a.get("type") or "") == "image_ref" and str(a.get("attachment_id") or "") for a in attachments)
    assert any(str(a.get("type") or "") == "image_url" and str(a.get("url") or "").endswith("/a.png") for a in attachments)
    body = json.loads(str(getattr(tool_rows[0], "content", "") or "{}"))
    content_items = ((body.get("result") or {}).get("content") or []) if isinstance(body, dict) else []
    image_block = next((x for x in content_items if isinstance(x, dict) and str(x.get("type") or "") == "image_ref"), {})
    assert str(image_block.get("attachment_id") or "")
    assert "data" not in image_block

