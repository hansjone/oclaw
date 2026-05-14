"""Admin tenant user stats (list_admin_user_stats) via SQLAlchemy Core."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, case, distinct, func, literal, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.sql import bindparam

from svc.persistence.db.tables import (
    app_user,
    auth_session,
    chat_session,
    trace_event,
    ui_session_owner,
)


class AdminUserStatsSaRepository:
    """Aggregates for ``SqliteStore.list_admin_user_stats``."""

    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def fetch(
        self,
        *,
        tenant_id: str,
        search_lower: str | None,
        cutoff_iso: str,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        tid = str(tenant_id or "").strip()
        lim = max(1, min(int(limit), 500))
        off = max(0, int(offset))
        q_text = str(search_lower or "").strip().lower() or None
        cutoff = str(cutoff_iso)

        conds: list[Any] = [app_user.c.tenant_id == tid]
        if q_text:
            like = f"%{q_text}%"
            conds.append(
                or_(
                    func.lower(func.coalesce(app_user.c.username, literal(""))).like(like),
                    func.lower(func.coalesce(app_user.c.display_name, literal(""))).like(like),
                )
            )
        wh = and_(*conds)

        user_stmt = (
            select(
                app_user.c.id.label("user_id"),
                app_user.c.username,
                func.coalesce(app_user.c.display_name, literal("")).label("display_name"),
                app_user.c.role,
                app_user.c.is_active,
            )
            .where(wh)
            .order_by(app_user.c.username.asc())
            .limit(lim)
            .offset(off)
        )
        cnt_stmt = select(func.count()).select_from(app_user).where(wh)

        sess_join = chat_session.join(
            ui_session_owner,
            ui_session_owner.c.session_id == chat_session.c.id,
        )
        active_ts = func.coalesce(chat_session.c.last_message_at, chat_session.c.created_at)
        total_active_sess_stmt = (
            select(func.count(distinct(chat_session.c.id)))
            .select_from(sess_join)
            .where(ui_session_owner.c.tenant_id == tid, active_ts >= literal(cutoff))
        )
        total_active_logins_stmt = (
            select(func.count())
            .select_from(auth_session)
            .where(
                auth_session.c.tenant_id == tid,
                auth_session.c.revoked_at.is_(None),
                auth_session.c.expires_at > literal(cutoff),
                auth_session.c.last_seen_at >= literal(cutoff),
            )
        )

        with self._engine.connect() as conn:
            total_users = int(conn.execute(cnt_stmt).scalar_one() or 0)
            user_rows = [dict(r) for r in conn.execute(user_stmt).mappings().all()]
            total_active_sessions = int(conn.execute(total_active_sess_stmt).scalar_one() or 0)
            total_active_logins = int(conn.execute(total_active_logins_stmt).scalar_one() or 0)

        uids = [str(r["user_id"] or "").strip() for r in user_rows if str(r.get("user_id") or "").strip()]
        trace_rows: list[dict[str, Any]] = []
        own_count_rows: list[dict[str, Any]] = []
        active_sess_rows: list[dict[str, Any]] = []
        login_rows: list[dict[str, Any]] = []

        if uids:
            uids_param = bindparam("uids", expanding=True)
            trace_stmt = (
                select(ui_session_owner.c.user_id, trace_event.c.payload)
                .select_from(
                    trace_event.join(
                        ui_session_owner,
                        ui_session_owner.c.session_id == trace_event.c.session_id,
                    )
                )
                .where(ui_session_owner.c.tenant_id == tid, ui_session_owner.c.user_id.in_(uids_param))
            )
            own_cnt_stmt = (
                select(ui_session_owner.c.user_id, func.count().label("c"))
                .where(ui_session_owner.c.tenant_id == tid, ui_session_owner.c.user_id.in_(uids_param))
                .group_by(ui_session_owner.c.user_id)
            )
            active_case = case(
                (active_ts >= literal(cutoff), chat_session.c.id),
                else_=None,
            )
            active_sess_stmt = (
                select(
                    ui_session_owner.c.user_id,
                    func.count(distinct(active_case)).label("active_30m"),
                    func.max(active_ts).label("last_message_at"),
                )
                .select_from(sess_join)
                .where(ui_session_owner.c.tenant_id == tid, ui_session_owner.c.user_id.in_(uids_param))
                .group_by(ui_session_owner.c.user_id)
            )
            login_stmt = (
                select(
                    auth_session.c.user_id,
                    func.count().label("c"),
                    func.max(auth_session.c.last_seen_at).label("last_seen_at"),
                )
                .where(
                    auth_session.c.tenant_id == tid,
                    auth_session.c.user_id.in_(uids_param),
                    auth_session.c.revoked_at.is_(None),
                    auth_session.c.expires_at > literal(cutoff),
                    auth_session.c.last_seen_at >= literal(cutoff),
                )
                .group_by(auth_session.c.user_id)
            )
            bind = {"uids": uids}
            with self._engine.connect() as conn:
                trace_rows = [dict(r) for r in conn.execute(trace_stmt, bind).mappings().all()]
                own_count_rows = [dict(r) for r in conn.execute(own_cnt_stmt, bind).mappings().all()]
                active_sess_rows = [dict(r) for r in conn.execute(active_sess_stmt, bind).mappings().all()]
                login_rows = [dict(r) for r in conn.execute(login_stmt, bind).mappings().all()]

        return {
            "total_users": total_users,
            "user_rows": user_rows,
            "total_active_sessions_30m": total_active_sessions,
            "total_active_logins_30m": total_active_logins,
            "trace_rows": trace_rows,
            "sessions_count_rows": own_count_rows,
            "active_sess_rows": active_sess_rows,
            "login_rows": login_rows,
        }


__all__ = ["AdminUserStatsSaRepository"]
