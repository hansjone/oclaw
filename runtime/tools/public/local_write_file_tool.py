from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.local_sdk import get_local_adapter


def local_write_file_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path") or "").strip()
        if not path:
            return {"ok": False, "error_code": "path_required", "error": "path_required"}
        content = str(args.get("content") or "")
        mode = str(args.get("mode") or "overwrite").strip().lower()
        return get_local_adapter().write_file(path=path, content=content, mode=mode)

    return ToolSpec(
        name="local_write_file",
        description="Write or append file content via local backend.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path."},
                "content": {"type": "string", "description": "Content to write."},
                "mode": {"type": "string", "enum": ["overwrite", "append"], "default": "overwrite"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "workspace", "write"}),
        risk_level="high",
        timeout_s=30.0,
        read_only=False,
    )


__all__ = ["local_write_file_tool"]
