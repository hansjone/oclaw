from __future__ import annotations

from pathlib import Path

from runtime.chat.tool_runtime import ToolExecutionContext, ToolExecutor, _maybe_auto_mark_xlsx_deliverable
from runtime.tools.base import ToolRegistry, ToolSpec
from svc.llm.chat_models import LLMToolCall
from svc.persistence.sqlite_store import SqliteStore


def test_helper_marks_on_whatsapp() -> None:
    out = _maybe_auto_mark_xlsx_deliverable(
        tool_name="write_xlsx",
        tool_args={},
        result={"ok": True, "attachment_id": "a1", "name": "r.xlsx"},
        inbound_metadata={"channel": "whatsapp"},
    )
    assert out.get("deliverable") is True
    assert out.get("auto_deliverable") is True


def test_helper_respects_explicit_false() -> None:
    out = _maybe_auto_mark_xlsx_deliverable(
        tool_name="write_xlsx",
        tool_args={"deliverable": False},
        result={"ok": True, "attachment_id": "a1"},
        inbound_metadata={"channel": "whatsapp"},
    )
    assert out.get("deliverable") is not True
    assert out.get("auto_deliverable") is not True


def test_helper_skips_non_channel() -> None:
    out = _maybe_auto_mark_xlsx_deliverable(
        tool_name="write_xlsx",
        tool_args={},
        result={"ok": True, "attachment_id": "a1"},
        inbound_metadata={"channel": "web"},
    )
    assert out.get("deliverable") is not True


def test_executor_auto_marks_write_xlsx_on_whatsapp(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    sess = store.create_session("t1")

    def handler(_args: dict) -> dict:
        return {
            "ok": True,
            "attachment_id": "att-xlsx",
            "name": "report.xlsx",
            "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

    reg = ToolRegistry(
        [
            ToolSpec(
                name="write_xlsx",
                description="xlsx",
                parameters={"type": "object", "properties": {}},
                handler=handler,
            )
        ]
    )
    ctx = ToolExecutionContext(
        store=store,
        tools=reg,
        session_id=sess.id,
        lang="en",
        inbound_metadata={"channel": "whatsapp"},
        turn_uuid="turn-xlsx-1",
    )
    out, _dur = ToolExecutor()._execute_tool(
        ctx,
        LLMToolCall(id="c1", name="write_xlsx", arguments={}),
    )
    assert out.get("ok") is True
    assert out.get("deliverable") is True
    assert out.get("auto_deliverable") is True
