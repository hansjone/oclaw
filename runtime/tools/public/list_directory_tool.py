from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.public.local_sdk import get_local_adapter


def list_directory_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path") or ".").strip() or "."
        max_entries = int(args.get("max_entries") or 500)
        return get_local_adapter().list_directory(path=path, max_entries=max_entries)

    return ToolSpec(
        name="list_directory",
        description="List a directory with file metadata (name/size/mtime).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": ".", "description": "Directory path."},
                "max_entries": {"type": "integer", "default": 500, "description": "Max entries to return."},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "workspace", "read"}),
        risk_level="low",
        read_only=True,
        timeout_s=10.0,
    )


__all__ = ["list_directory_tool"]
