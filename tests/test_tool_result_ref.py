from __future__ import annotations

from pathlib import Path

from runtime.chat.tool_result_store import (
    attach_result_ref,
    load_tool_result_blob,
    save_tool_result_blob,
)
from runtime.tools.public.fetch_tool_result_tool import fetch_tool_result_tool


def test_save_and_fetch_tool_result_blob(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("runtime.chat.tool_result_store.attachments_dir", lambda: tmp_path)
    big = {"ok": True, "rows": ["x" * 100 for _ in range(80)]}
    ref = save_tool_result_blob(session_id="sess-1", tool_call_id="tc1", result=big)
    assert ref and ref.startswith("tr:")
    loaded = load_tool_result_blob(ref, session_id="sess-1")
    assert loaded["ok"] is True
    assert loaded["result"]["ok"] is True
    assert loaded["truncated"] is False


def test_attach_result_ref_adds_fetch_hint() -> None:
    out = attach_result_ref({"ok": True, "_truncated_for_llm": True, "preview": "p"}, result_ref="tr:abcd")
    assert out["result_ref"] == "tr:abcd"
    assert out["fetch_tool"] == "fetch_tool_result"
    assert "fetch_tool_result" in str(out.get("hint") or "")


def test_fetch_tool_result_public_tool(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("runtime.chat.tool_result_store.attachments_dir", lambda: tmp_path)
    ref = save_tool_result_blob(
        session_id="sess-2",
        tool_call_id="tc2",
        result={"ok": True, "data": "hello" * 2000},
        force=True,
    )
    assert ref
    monkeypatch.setattr(
        "runtime.tools.public.fetch_tool_result_tool.current_tool_lane_sessions",
        lambda: (None, "sess-2"),
    )
    tool = fetch_tool_result_tool()
    out = tool.handler({"result_ref": ref})
    assert out["ok"] is True
    assert out["result_ref"] == ref
