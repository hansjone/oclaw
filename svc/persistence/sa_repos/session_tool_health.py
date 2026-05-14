"""Session tool health listing (admin) via SQLAlchemy Core."""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, literal, select
from sqlalchemy.engine import Engine

from svc.persistence.db.tables import chat_message, chat_session, tool_log


class SessionToolHealthSaRepository:
    """``list_session_tool_health`` aggregates."""

    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list_session_tool_health(
        self, *, session_id: str | None, limit: int
    ) -> list[dict[str, Any]]:
        lim = max(1, int(limit))
        msg_sq = (
            select(
                chat_message.c.session_id,
                func.sum(case((chat_message.c.role == literal("user"), 1), else_=0)).label("user_count"),
                func.sum(case((chat_message.c.role == literal("assistant"), 1), else_=0)).label(
                    "assistant_count"
                ),
            )
            .group_by(chat_message.c.session_id)
            .subquery()
        )
        tl_sq = (
            select(
                tool_log.c.session_id,
                func.count(1).label("tool_count"),
                func.sum(case((tool_log.c.tool_name.like("mcp__%"), 1), else_=0)).label(
                    "mcp_tool_count"
                ),
                func.max(tool_log.c.timestamp).label("last_tool_at"),
            )
            .group_by(tool_log.c.session_id)
            .subquery()
        )
        stmt = (
            select(
                chat_session.c.id.label("session_id"),
                chat_session.c.title,
                chat_session.c.last_message_at,
                func.coalesce(msg_sq.c.user_count, literal(0)).label("user_count"),
                func.coalesce(msg_sq.c.assistant_count, literal(0)).label("assistant_count"),
                func.coalesce(tl_sq.c.tool_count, literal(0)).label("tool_count"),
                func.coalesce(tl_sq.c.mcp_tool_count, literal(0)).label("mcp_tool_count"),
                func.coalesce(tl_sq.c.last_tool_at, literal("")).label("last_tool_at"),
            )
            .select_from(
                chat_session.outerjoin(msg_sq, msg_sq.c.session_id == chat_session.c.id).outerjoin(
                    tl_sq, tl_sq.c.session_id == chat_session.c.id
                )
            )
            .order_by(
                func.coalesce(chat_session.c.last_message_at, chat_session.c.created_at).desc(),
            )
            .limit(lim)
        )
        sid = str(session_id or "").strip()
        if sid:
            stmt = stmt.where(chat_session.c.id == sid)
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [dict(r) for r in rows]


__all__ = ["SessionToolHealthSaRepository"]
