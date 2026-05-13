from __future__ import annotations

from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.public.local_sdk import get_local_adapter


def get_cwd_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        del args
        return get_local_adapter().get_cwd()

    return ToolSpec(
        name="get_cwd",
        description="Get current working directory for local tools.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=_handler,
        tags=frozenset({"public", "local", "read"}),
        risk_level="low",
        read_only=True,
        timeout_s=2.0,
    )


__all__ = ["get_cwd_tool"]
