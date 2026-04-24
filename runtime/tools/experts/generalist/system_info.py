from __future__ import annotations

import datetime
import time
from typing import Any

from oclaw.runtime.tools.base import ToolSpec


def system_info_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        now = datetime.datetime.now()
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        timezone_name = time.tzname[0] if time.daylight == 0 else time.tzname[1]
        timezone_offset = (now - utc_now.replace(tzinfo=None)).total_seconds() / 3600
        return {
            "ok": True,
            "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": timezone_name,
            "timezone_offset": f"UTC{'+' if timezone_offset >= 0 else ''}{timezone_offset:g}",
            "timestamp": int(time.time()),
        }

    return ToolSpec(
        name="get_system_time",
        description="Return the current local time, timezone name, and UTC offset.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=handler,
        read_only=True,
    )


__all__ = ["system_info_tool"]
