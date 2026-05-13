from __future__ import annotations

import time
from typing import Any


def emit_plan_agent_v2_trace(
    *,
    store: Any,
    session_id: str,
    trace_id: str | None,
    parent_span_id: str | None,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    if not str(trace_id or "").strip():
        return
    merged = dict(payload or {})
    merged.setdefault("pipeline", "plan_agent_v2")
    merged.setdefault("ts_ms", int(time.time() * 1000))
    try:
        from runtime.orchestration.trace import new_span_id

        store.add_trace_event(
            session_id=str(session_id or ""),
            trace_id=str(trace_id),
            span_id=new_span_id(),
            parent_span_id=parent_span_id,
            event_type=str(event_type or "plan_agent_v2"),
            payload=merged,
        )
    except Exception:
        pass


__all__ = ["emit_plan_agent_v2_trace"]

