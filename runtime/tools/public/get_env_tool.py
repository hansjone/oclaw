from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.local_sdk import get_local_adapter


def get_env_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        key = str(args.get("key") or "").strip()
        default = args.get("default")
        return get_local_adapter().get_env(key=key, default=str(default) if default is not None else None)

    return ToolSpec(
        name="get_env",
        description="Get an environment variable value.",
        parameters={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Environment variable key."},
                "default": {"type": "string", "description": "Default value if missing."},
            },
            "required": ["key"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "read"}),
        risk_level="low",
        read_only=True,
        timeout_s=2.0,
    )


__all__ = ["get_env_tool"]
