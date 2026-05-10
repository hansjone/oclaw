from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.public.local_sdk import get_local_adapter


def set_env_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        key = str(args.get("key") or "").strip()
        value = args.get("value")
        return get_local_adapter().set_env(key=key, value=str(value) if value is not None else None)

    return ToolSpec(
        name="set_env",
        description="Set or delete an environment variable in the current process.",
        parameters={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Environment variable key."},
                "value": {"type": "string", "description": "Value to set. If omitted, deletes the key."},
            },
            "required": ["key"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "write"}),
        risk_level="high",
        timeout_s=2.0,
    )


__all__ = ["set_env_tool"]
