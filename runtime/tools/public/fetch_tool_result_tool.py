from __future__ import annotations

from typing import Any

from runtime.chat.tool_invocation_context import current_tool_lane_sessions
from runtime.chat.tool_result_store import load_tool_result_blob
from runtime.tools.base import ToolSpec


def fetch_tool_result_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        ref = str(args.get("result_ref") or "").strip()
        if not ref:
            return {"ok": False, "error_code": "result_ref_required", "error": "result_ref_required"}
        owner, sid = current_tool_lane_sessions()
        session_id = str(sid or owner or "").strip()
        max_chars = args.get("max_chars")
        try:
            max_i = int(max_chars) if max_chars is not None else None
        except Exception:
            max_i = None
        return load_tool_result_blob(ref, session_id=session_id, max_chars=max_i)

    return ToolSpec(
        name="fetch_tool_result",
        description=(
            "Fetch a previously truncated/guarded tool result by result_ref. "
            "Use when a tool payload includes result_ref / _truncated_for_llm / _tool_result_guarded "
            "and you need more detail than the compact preview."
        ),
        parameters={
            "type": "object",
            "properties": {
                "result_ref": {
                    "type": "string",
                    "description": "Opaque ref from a prior tool message (e.g. tr:…).",
                },
                "max_chars": {
                    "type": "integer",
                    "minimum": 4000,
                    "maximum": 500000,
                    "description": "Optional cap for returned JSON size (default ~120k).",
                },
            },
            "required": ["result_ref"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"system", "read", "tool_result"}),
        read_only=True,
        risk_level="low",
        timeout_s=8.0,
    )


__all__ = ["fetch_tool_result_tool"]
