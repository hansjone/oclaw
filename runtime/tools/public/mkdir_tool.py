from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.local_sdk import get_local_adapter


def mkdir_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path") or "").strip()
        parents = bool(args.get("parents", True))
        exist_ok = bool(args.get("exist_ok", True))
        return get_local_adapter().mkdir(path=path, parents=parents, exist_ok=exist_ok)

    return ToolSpec(
        name="mkdir",
        description="Create a directory inside the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to create."},
                "parents": {"type": "boolean", "default": True},
                "exist_ok": {"type": "boolean", "default": True},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "workspace", "write"}),
        risk_level="high",
        timeout_s=10.0,
    )


__all__ = ["mkdir_tool"]
