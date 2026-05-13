from __future__ import annotations

from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.public.local_sdk import get_local_adapter


def delete_file_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path") or "").strip()
        missing_ok = bool(args.get("missing_ok", True))
        return get_local_adapter().delete_path(path=path, missing_ok=missing_ok)

    return ToolSpec(
        name="delete_file",
        description="Delete a file or directory inside the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to delete."},
                "missing_ok": {"type": "boolean", "default": True, "description": "If true, missing path is ok."},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "workspace", "write"}),
        risk_level="high",
        timeout_s=20.0,
    )


__all__ = ["delete_file_tool"]
