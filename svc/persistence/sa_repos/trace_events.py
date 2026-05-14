"""trace_event insert + list queries via SQLAlchemy Core."""

from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from svc.persistence.db.tables import trace_event


class TraceEventsSaRepository:
    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def insert_one(
        self,
        *,
        session_id: str,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None,
        event_type: str,
        payload: str,
        timestamp: str,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(trace_event).values(
                    session_id=str(session_id),
                    trace_id=str(trace_id),
                    span_id=str(span_id),
                    parent_span_id=parent_span_id,
                    event_type=str(event_type),
                    payload=str(payload),
                    timestamp=str(timestamp),
                )
            )

    def insert_many(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        with self._engine.begin() as conn:
            conn.execute(insert(trace_event), rows)

    def list_trace_events_desc(self, *, session_id: str, limit: int) -> list[dict[str, Any]]:
        sid = str(session_id or "").strip()
        lim = max(1, int(limit))
        stmt = (
            select(
                trace_event.c.trace_id,
                trace_event.c.span_id,
                trace_event.c.parent_span_id,
                trace_event.c.event_type,
                trace_event.c.payload,
                trace_event.c.timestamp,
            )
            .where(trace_event.c.session_id == sid)
            .order_by(trace_event.c.id.desc())
            .limit(lim)
        )
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings().all()]

    def list_trace_events_for_trace_asc(
        self, *, session_id: str, trace_id: str, limit: int
    ) -> list[dict[str, Any]]:
        sid = str(session_id or "").strip()
        tid = str(trace_id or "").strip()
        lim = max(1, int(limit))
        if not sid or not tid:
            return []
        stmt = (
            select(
                trace_event.c.trace_id,
                trace_event.c.span_id,
                trace_event.c.parent_span_id,
                trace_event.c.event_type,
                trace_event.c.payload,
                trace_event.c.timestamp,
            )
            .where(trace_event.c.session_id == sid, trace_event.c.trace_id == tid)
            .order_by(trace_event.c.id.asc())
            .limit(lim)
        )
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings().all()]

    def list_event_type_timestamp_for_trace(
        self, *, session_id: str, trace_id: str
    ) -> list[dict[str, Any]]:
        sid = str(session_id or "").strip()
        tid = str(trace_id or "").strip()
        if not sid or not tid:
            return []
        stmt = (
            select(trace_event.c.event_type, trace_event.c.timestamp)
            .where(trace_event.c.session_id == sid, trace_event.c.trace_id == tid)
            .order_by(trace_event.c.id.asc())
        )
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings().all()]


__all__ = ["TraceEventsSaRepository"]
