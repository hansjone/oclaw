from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.local_sdk import get_local_adapter


def kill_process_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        pid = int(args.get("pid") or 0)
        force = bool(args.get("force", True))
        return get_local_adapter().kill_process(pid=pid, force=force)

    return ToolSpec(
        name="kill_process",
        description="Kill a process by PID (best-effort).",
        parameters={
            "type": "object",
            "properties": {
                "pid": {"type": "integer", "description": "Process id."},
                "force": {"type": "boolean", "default": True, "description": "Force kill if true."},
            },
            "required": ["pid"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "write"}),
        risk_level="high",
        timeout_s=10.0,
    )


__all__ = ["kill_process_tool"]
