from __future__ import annotations

from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.public.local_sdk import get_local_adapter


def list_processes_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        max_results = int(args.get("max_results") or 200)
        return get_local_adapter().list_processes(max_results=max_results)

    return ToolSpec(
        name="list_processes",
        description="List running processes (best-effort).",
        parameters={
            "type": "object",
            "properties": {"max_results": {"type": "integer", "default": 200}},
            "required": [],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "read"}),
        risk_level="low",
        read_only=True,
        timeout_s=10.0,
    )


__all__ = ["list_processes_tool"]
