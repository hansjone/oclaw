from __future__ import annotations

import time
from typing import Any

from runtime.tools.base import ToolSpec

_MAX_SLEEP_S = 120


def sleep_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            seconds = float(args.get("seconds") or 0)
        except Exception:
            return {"ok": False, "error": "invalid_seconds"}
        if seconds <= 0:
            return {"ok": False, "error": "seconds_must_be_positive"}
        if seconds > _MAX_SLEEP_S:
            return {
                "ok": False,
                "error": "seconds_too_large",
                "max_seconds": _MAX_SLEEP_S,
                "hint": (
                    "For multi-hour work use start_job + get_job, or schedule_create. "
                    f"sleep is only for short poll gaps (max {_MAX_SLEEP_S}s)."
                ),
            }
        started = time.time()
        time.sleep(seconds)
        return {
            "ok": True,
            "slept_seconds": round(time.time() - started, 3),
            "requested_seconds": seconds,
        }

    return ToolSpec(
        name="sleep",
        description=(
            f"Block the current turn for N seconds (max {_MAX_SLEEP_S}). "
            "Use between get_job polls or after a change that needs a short settle time. "
            "Do NOT use for multi-hour waits — use start_job or schedule_create instead."
        ),
        parameters={
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": f"Seconds to wait (1–{_MAX_SLEEP_S}).",
                },
            },
            "required": ["seconds"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "utility"}),
        risk_level="low",
        read_only=True,
        timeout_s=float(_MAX_SLEEP_S + 5),
    )


__all__ = ["sleep_tool"]
