from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from oclaw.tools.base import ToolSpec


def system_time_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        del args
        now = datetime.now(timezone.utc)
        return {
            "ok": True,
            "utc_iso": now.isoformat().replace("+00:00", "Z"),
            "unix_ms": int(now.timestamp() * 1000),
        }

    return ToolSpec(
        name="system_time",
        description="Return current system time (UTC).",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=_handler,
        tags=frozenset({"system", "time", "read"}),
        read_only=True,
        risk_level="low",
        timeout_s=2.0,
    )


__all__ = ["system_time_tool"]

