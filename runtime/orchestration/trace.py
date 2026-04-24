from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any


def new_trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:20]}"


def new_span_id() -> str:
    return f"sp_{uuid.uuid4().hex[:16]}"


def estimate_tokens(text: str) -> int:
    # rough heuristic: ~4 chars per token for English-ish; Chinese is denser but ok for hint.
    s = (text or "").strip()
    return max(0, int(len(s) / 4))


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    span_id: str
    parent_span_id: str | None = None


class TraceEmitter:
    def __init__(self, store: Any):
        self.store = store

    def emit(
        self,
        *,
        session_id: str,
        ctx: TraceContext,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        try:
            self.store.add_trace_event(
                session_id=session_id,
                trace_id=ctx.trace_id,
                span_id=ctx.span_id,
                parent_span_id=ctx.parent_span_id,
                event_type=event_type,
                payload=payload or {},
            )
        except Exception:
            return


__all__ = ["TraceContext", "TraceEmitter", "new_trace_id", "new_span_id", "estimate_tokens"]

