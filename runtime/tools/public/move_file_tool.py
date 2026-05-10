from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.public.local_sdk import get_local_adapter


def move_file_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        src = str(args.get("src") or "").strip()
        dst = str(args.get("dst") or "").strip()
        overwrite = bool(args.get("overwrite", False))
        return get_local_adapter().move_path(src=src, dst=dst, overwrite=overwrite)

    return ToolSpec(
        name="move_file",
        description="Move/rename a file or directory inside the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "Source path."},
                "dst": {"type": "string", "description": "Destination path."},
                "overwrite": {"type": "boolean", "default": False, "description": "Overwrite destination if exists."},
            },
            "required": ["src", "dst"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "workspace", "write"}),
        risk_level="high",
        timeout_s=20.0,
    )


__all__ = ["move_file_tool"]
