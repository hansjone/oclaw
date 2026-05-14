"""tool_log read paths (MCP summaries, call logs) via SQLAlchemy Core."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, delete, exists, func, insert, select, update
from sqlalchemy.engine import Engine

from svc.persistence.db.tables import chat_session, tool_log


class ToolLogQueriesSaRepository:
    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def insert_tool_log(
        self,
        *,
        session_id: str,
        tool_name: str,
        specialist: str,
        args: str,
        result: str,
        timestamp: str,
        duration_ms: int | None,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(tool_log).values(
                    session_id=str(session_id),
                    tool_name=str(tool_name),
                    specialist=str(specialist or ""),
                    args=str(args),
                    result=str(result),
                    timestamp=str(timestamp),
                    duration_ms=duration_ms,
                )
            )

    def list_tool_logs_asc(self, *, session_id: str, limit: int) -> list[dict[str, Any]]:
        sid = str(session_id or "").strip()
        lim = max(1, int(limit))
        stmt = (
            select(
                tool_log.c.tool_name,
                tool_log.c.specialist,
                tool_log.c.args,
                tool_log.c.result,
                tool_log.c.timestamp,
                tool_log.c.duration_ms,
            )
            .where(tool_log.c.session_id == sid)
            .order_by(tool_log.c.id.asc())
            .limit(lim)
        )
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings().all()]

    def move_tool_logs_between_sessions(self, *, from_session_id: str, to_session_id: str) -> int:
        src = str(from_session_id or "").strip()
        dst = str(to_session_id or "").strip()
        if not src or not dst or src == dst:
            return 0
        with self._engine.begin() as conn:
            res = conn.execute(
                update(tool_log)
                .where(tool_log.c.session_id == src)
                .values(session_id=dst)
            )
            return int(res.rowcount or 0)

    def delete_tool_logs_where_session_missing(self) -> int:
        """Delete ``tool_log`` rows whose ``session_id`` is not in ``chat_session`` (housekeeping)."""
        sess_exists = exists(
            select(1).select_from(chat_session).where(chat_session.c.id == tool_log.c.session_id)
        )
        with self._engine.begin() as conn:
            res = conn.execute(delete(tool_log).where(~sess_exists))
            return int(res.rowcount or 0)

    def list_mcp_tool_usage_summary(self, *, limit: int) -> list[dict[str, Any]]:
        lim = max(1, int(limit))
        n = func.count(1).label("n")
        last_ts = func.max(tool_log.c.timestamp).label("last_ts")
        stmt = (
            select(tool_log.c.tool_name, tool_log.c.specialist, n, last_ts)
            .where(tool_log.c.tool_name.like("mcp__%"))
            .group_by(tool_log.c.tool_name, tool_log.c.specialist)
            .order_by(n.desc(), last_ts.desc())
            .limit(lim)
        )
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings().all()]

    def list_mcp_tool_aggregate_usage(self) -> list[dict[str, Any]]:
        n = func.count(1).label("n")
        last_ts = func.max(tool_log.c.timestamp).label("last_ts")
        stmt = (
            select(tool_log.c.tool_name, n, last_ts)
            .where(tool_log.c.tool_name.like("mcp__%"))
            .group_by(tool_log.c.tool_name)
        )
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings().all()]

    def list_mcp_tool_call_logs(self, *, server_id: str | None, limit: int) -> list[dict[str, Any]]:
        lim = max(1, int(limit))
        sid = str(server_id or "").strip()
        conds = [tool_log.c.tool_name.like("mcp__%")]
        if sid:
            conds.append(tool_log.c.tool_name.like(f"mcp__{sid}__%"))
        stmt = (
            select(
                tool_log.c.session_id,
                tool_log.c.tool_name,
                tool_log.c.specialist,
                tool_log.c.args,
                tool_log.c.result,
                tool_log.c.timestamp,
                tool_log.c.duration_ms,
            )
            .where(and_(*conds))
            .order_by(tool_log.c.id.desc())
            .limit(lim)
        )
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings().all()]


__all__ = ["ToolLogQueriesSaRepository"]
