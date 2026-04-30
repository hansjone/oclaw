from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.local_sdk import get_local_adapter


def local_read_file_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path") or "").strip()
        if not path:
            return {"ok": False, "error_code": "path_required", "error": "path_required"}
        start_line = args.get("start_line")
        end_line = args.get("end_line")
        return get_local_adapter().read_file(
            path=path,
            start_line=int(start_line) if start_line is not None else None,
            end_line=int(end_line) if end_line is not None else None,
        )

    return ToolSpec(
        name="local_read_file",
        description="Read file content via local backend.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path."},
                "start_line": {"type": "integer", "description": "Optional start line (1-indexed)."},
                "end_line": {"type": "integer", "description": "Optional end line (1-indexed)."},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "workspace", "read"}),
        risk_level="low",
        timeout_s=20.0,
        read_only=True,
    )


__all__ = ["local_read_file_tool"]
