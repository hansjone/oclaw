from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.public.local_sdk import get_local_adapter


def run_command_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        command = str(args.get("command") or "").strip()
        if not command:
            return {"ok": False, "error_code": "command_required", "error": "command_required"}
        cwd = str(args.get("cwd") or "").strip() or None
        timeout = int(args.get("timeout") or 300)
        return get_local_adapter().run_command(command=command, cwd=cwd, timeout=timeout)

    return ToolSpec(
        name="run_command",
        description="Run a shell command via local backend.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute."},
                "cwd": {"type": "string", "description": "Optional working directory."},
                "timeout": {"type": "integer", "description": "Timeout in seconds.", "default": 300},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "exec"}),
        risk_level="high",
        timeout_s=620.0,
        read_only=False,
    )


__all__ = ["run_command_tool"]
