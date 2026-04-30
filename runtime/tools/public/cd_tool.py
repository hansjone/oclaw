from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.local_sdk import get_local_adapter


def cd_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        cwd = str(args.get("cwd") or "").strip()
        return get_local_adapter().cd(cwd=cwd)

    return ToolSpec(
        name="cd",
        description="Change current working directory for local tools (best-effort, per-process).",
        parameters={
            "type": "object",
            "properties": {"cwd": {"type": "string", "description": "Directory to change into."}},
            "required": ["cwd"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "write"}),
        risk_level="high",
        timeout_s=5.0,
    )


__all__ = ["cd_tool"]
