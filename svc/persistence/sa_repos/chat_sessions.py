"""chat_session (+ ui_session_owner joins) via SQLAlchemy Core."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import and_, delete, distinct, func, insert, literal, or_, select, update
from sqlalchemy.engine import Engine

from svc.persistence.db.tables import app_user, channel_session_v2, chat_message, chat_session, ui_session_owner
from svc.persistence.sqlite_store import ChatSession, SessionsListMeta


def _session_from_row(row: Mapping[str, Any]) -> ChatSession:
    return ChatSession(
        id=str(row["id"]),
        title=str(row["title"]),
        created_at=str(row["created_at"]),
        last_message_at=row["last_message_at"],
    )


def _activity_order() -> tuple[Any, Any]:
    return (
        func.coalesce(chat_session.c.last_message_at, chat_session.c.created_at).desc(),
        chat_session.c.created_at.desc(),
    )


class ChatSessionsSaRepository:
    """Phase-3 SA migration: chat session rows and list queries (messages stay raw SQL for now)."""

    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def insert_chat_session(self, *, session_id: str, title: str, created_at: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(chat_session).values(
                    id=str(session_id),
                    title=str(title),
                    created_at=str(created_at),
                    last_message_at=None,
                )
            )

    def fetch_chat_session_by_id(self, *, session_id: str) -> ChatSession | None:
        sid = str(session_id or "").strip()
        if not sid:
            return None
        with self._engine.connect() as conn:
            row = conn.execute(
                select(
                    chat_session.c.id,
                    chat_session.c.title,
                    chat_session.c.created_at,
                    chat_session.c.last_message_at,
                )
                .where(chat_session.c.id == sid)
                .limit(1)
            ).mappings().first()
        return _session_from_row(row) if row else None

    def fetch_chat_session_for_user(
        self, *, session_id: str, tenant_id: str, user_id: str
    ) -> ChatSession | None:
        sid = str(session_id or "").strip()
        if not sid:
            return None
        tid, uid = str(tenant_id), str(user_id)
        with self._engine.connect() as conn:
            row = conn.execute(
                select(
                    chat_session.c.id,
                    chat_session.c.title,
                    chat_session.c.created_at,
                    chat_session.c.last_message_at,
                )
                .select_from(
                    chat_session.join(
                        ui_session_owner,
                        ui_session_owner.c.session_id == chat_session.c.id,
                    )
                )
                .where(
                    chat_session.c.id == sid,
                    ui_session_owner.c.tenant_id == tid,
                    ui_session_owner.c.user_id == uid,
                )
                .limit(1)
            ).mappings().first()
        return _session_from_row(row) if row else None

    def list_chat_sessions_global(self, *, limit: int | None, offset: int) -> list[ChatSession]:
        stmt = select(
            chat_session.c.id,
            chat_session.c.title,
            chat_session.c.created_at,
            chat_session.c.last_message_at,
        ).order_by(*_activity_order())
        if limit is not None:
            stmt = stmt.limit(int(limit)).offset(int(offset))
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_session_from_row(r) for r in rows]

    def list_chat_sessions_for_user(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int | None,
        offset: int,
    ) -> list[ChatSession]:
        tid, uid = str(tenant_id), str(user_id)
        stmt = (
            select(
                chat_session.c.id,
                chat_session.c.title,
                chat_session.c.created_at,
                chat_session.c.last_message_at,
            )
            .select_from(
                chat_session.join(
                    ui_session_owner,
                    ui_session_owner.c.session_id == chat_session.c.id,
                )
            )
            .where(
                ui_session_owner.c.tenant_id == tid,
                ui_session_owner.c.user_id == uid,
            )
            .order_by(*_activity_order())
        )
        if limit is not None:
            stmt = stmt.limit(int(limit)).offset(int(offset))
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_session_from_row(r) for r in rows]

    def list_chat_sessions_for_tenant(
        self,
        *,
        tenant_id: str,
        limit: int | None,
        offset: int,
    ) -> list[ChatSession]:
        tid = str(tenant_id)
        stmt = (
            select(
                chat_session.c.id,
                chat_session.c.title,
                chat_session.c.created_at,
                chat_session.c.last_message_at,
            )
            .select_from(
                chat_session.join(
                    ui_session_owner,
                    ui_session_owner.c.session_id == chat_session.c.id,
                )
            )
            .where(ui_session_owner.c.tenant_id == tid)
            .distinct()
            .order_by(*_activity_order())
        )
        if limit is not None:
            stmt = stmt.limit(int(limit)).offset(int(offset))
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_session_from_row(r) for r in rows]

    def count_chat_sessions_global(self) -> int:
        with self._engine.connect() as conn:
            n = conn.execute(select(func.count()).select_from(chat_session)).scalar_one()
        return int(n or 0)

    def sessions_list_meta_global(self) -> SessionsListMeta:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(
                    func.count().label("c"),
                    func.max(
                        func.coalesce(chat_session.c.last_message_at, chat_session.c.created_at)
                    ).label("latest_activity_at"),
                ).select_from(chat_session)
            ).mappings().first()
        return SessionsListMeta(
            session_count=int(row["c"] or 0) if row else 0,
            latest_activity_at=str(row["latest_activity_at"])
            if row and row.get("latest_activity_at") is not None
            else None,
        )

    def _administrator_username_predicate(self, username: str) -> Any:
        uname = str(username or "").strip().lower()
        return func.lower(app_user.c.username) == uname

    def _administrator_chat_session_ids_subquery(self, *, username: str, tenant_id: str) -> Any:
        pred = self._administrator_username_predicate(username)
        tid = str(tenant_id or "").strip()
        admin_ids = (
            select(chat_session.c.id.label("sid"))
            .select_from(
                chat_session.join(
                    ui_session_owner,
                    ui_session_owner.c.session_id == chat_session.c.id,
                ).join(
                    app_user,
                    and_(
                        app_user.c.id == ui_session_owner.c.user_id,
                        app_user.c.tenant_id == ui_session_owner.c.tenant_id,
                    ),
                )
            )
            .where(pred)
        )
        channel_ids = (
            select(channel_session_v2.c.session_id.label("sid"))
            .where(
                channel_session_v2.c.tenant_id == tid,
                channel_session_v2.c.session_id.isnot(None),
                channel_session_v2.c.session_id != "",
            )
        )
        return admin_ids.union(channel_ids).subquery()

    def list_chat_sessions_for_administrator_chat_view(
        self,
        *,
        username: str,
        tenant_id: str,
        limit: int | None,
        offset: int,
    ) -> list[ChatSession]:
        ids = self._administrator_chat_session_ids_subquery(
            username=username, tenant_id=tenant_id
        )
        stmt = (
            select(
                chat_session.c.id,
                chat_session.c.title,
                chat_session.c.created_at,
                chat_session.c.last_message_at,
            )
            .where(chat_session.c.id.in_(select(ids.c.sid)))
            .order_by(*_activity_order())
        )
        if limit is not None:
            stmt = stmt.limit(int(limit)).offset(int(offset))
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_session_from_row(r) for r in rows]

    def sessions_list_meta_for_administrator_chat_view(
        self, *, username: str, tenant_id: str
    ) -> SessionsListMeta:
        ids = self._administrator_chat_session_ids_subquery(
            username=username, tenant_id=tenant_id
        )
        with self._engine.connect() as conn:
            row = conn.execute(
                select(
                    func.count().label("c"),
                    func.max(
                        func.coalesce(chat_session.c.last_message_at, chat_session.c.created_at)
                    ).label("latest_activity_at"),
                )
                .select_from(chat_session)
                .where(chat_session.c.id.in_(select(ids.c.sid)))
            ).mappings().first()
        return SessionsListMeta(
            session_count=int(row["c"] or 0) if row else 0,
            latest_activity_at=str(row["latest_activity_at"])
            if row and row.get("latest_activity_at") is not None
            else None,
        )

    def fetch_chat_session_for_administrator_chat_view(
        self, *, session_id: str, username: str, tenant_id: str
    ) -> ChatSession | None:
        sid = str(session_id or "").strip()
        if not sid:
            return None
        ids = self._administrator_chat_session_ids_subquery(
            username=username, tenant_id=tenant_id
        )
        with self._engine.connect() as conn:
            row = conn.execute(
                select(
                    chat_session.c.id,
                    chat_session.c.title,
                    chat_session.c.created_at,
                    chat_session.c.last_message_at,
                )
                .where(chat_session.c.id == sid, chat_session.c.id.in_(select(ids.c.sid)))
                .limit(1)
            ).mappings().first()
        return _session_from_row(row) if row else None

    def list_chat_sessions_for_administrator_username(
        self,
        *,
        username: str,
        limit: int | None,
        offset: int,
    ) -> list[ChatSession]:
        """All sessions owned by any ``app_user`` row with this login name (cross-tenant)."""
        pred = self._administrator_username_predicate(username)
        stmt = (
            select(
                chat_session.c.id,
                chat_session.c.title,
                chat_session.c.created_at,
                chat_session.c.last_message_at,
            )
            .select_from(
                chat_session.join(
                    ui_session_owner,
                    ui_session_owner.c.session_id == chat_session.c.id,
                ).join(
                    app_user,
                    and_(
                        app_user.c.id == ui_session_owner.c.user_id,
                        app_user.c.tenant_id == ui_session_owner.c.tenant_id,
                    ),
                )
            )
            .where(pred)
            .order_by(*_activity_order())
        )
        if limit is not None:
            stmt = stmt.limit(int(limit)).offset(int(offset))
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_session_from_row(r) for r in rows]

    def sessions_list_meta_for_administrator_username(self, *, username: str) -> SessionsListMeta:
        pred = self._administrator_username_predicate(username)
        with self._engine.connect() as conn:
            row = conn.execute(
                select(
                    func.count(distinct(chat_session.c.id)).label("c"),
                    func.max(
                        func.coalesce(chat_session.c.last_message_at, chat_session.c.created_at)
                    ).label("latest_activity_at"),
                )
                .select_from(
                    chat_session.join(
                        ui_session_owner,
                        ui_session_owner.c.session_id == chat_session.c.id,
                    ).join(
                        app_user,
                        and_(
                            app_user.c.id == ui_session_owner.c.user_id,
                            app_user.c.tenant_id == ui_session_owner.c.tenant_id,
                        ),
                    )
                )
                .where(pred)
            ).mappings().first()
        return SessionsListMeta(
            session_count=int(row["c"] or 0) if row else 0,
            latest_activity_at=str(row["latest_activity_at"])
            if row and row.get("latest_activity_at") is not None
            else None,
        )

    def fetch_chat_session_for_administrator_username(
        self, *, session_id: str, username: str
    ) -> ChatSession | None:
        sid = str(session_id or "").strip()
        if not sid:
            return None
        pred = self._administrator_username_predicate(username)
        with self._engine.connect() as conn:
            row = conn.execute(
                select(
                    chat_session.c.id,
                    chat_session.c.title,
                    chat_session.c.created_at,
                    chat_session.c.last_message_at,
                )
                .select_from(
                    chat_session.join(
                        ui_session_owner,
                        ui_session_owner.c.session_id == chat_session.c.id,
                    ).join(
                        app_user,
                        and_(
                            app_user.c.id == ui_session_owner.c.user_id,
                            app_user.c.tenant_id == ui_session_owner.c.tenant_id,
                        ),
                    )
                )
                .where(chat_session.c.id == sid, pred)
                .limit(1)
            ).mappings().first()
        return _session_from_row(row) if row else None

    def sessions_list_meta_for_user(self, *, tenant_id: str, user_id: str) -> SessionsListMeta:
        tid, uid = str(tenant_id), str(user_id)
        with self._engine.connect() as conn:
            row = conn.execute(
                select(
                    func.count().label("c"),
                    func.max(
                        func.coalesce(chat_session.c.last_message_at, chat_session.c.created_at)
                    ).label("latest_activity_at"),
                )
                .select_from(
                    chat_session.join(
                        ui_session_owner,
                        ui_session_owner.c.session_id == chat_session.c.id,
                    )
                )
                .where(
                    ui_session_owner.c.tenant_id == tid,
                    ui_session_owner.c.user_id == uid,
                )
            ).mappings().first()
        return SessionsListMeta(
            session_count=int(row["c"] or 0) if row else 0,
            latest_activity_at=str(row["latest_activity_at"])
            if row and row.get("latest_activity_at") is not None
            else None,
        )

    def sessions_list_meta_for_tenant(self, *, tenant_id: str) -> SessionsListMeta:
        tid = str(tenant_id)
        with self._engine.connect() as conn:
            row = conn.execute(
                select(
                    func.count(distinct(chat_session.c.id)).label("c"),
                    func.max(
                        func.coalesce(chat_session.c.last_message_at, chat_session.c.created_at)
                    ).label("latest_activity_at"),
                )
                .select_from(
                    chat_session.join(
                        ui_session_owner,
                        ui_session_owner.c.session_id == chat_session.c.id,
                    )
                )
                .where(ui_session_owner.c.tenant_id == tid)
            ).mappings().first()
        return SessionsListMeta(
            session_count=int(row["c"] or 0) if row else 0,
            latest_activity_at=str(row["latest_activity_at"])
            if row and row.get("latest_activity_at") is not None
            else None,
        )

    def fetch_chat_session_in_tenant(self, *, session_id: str, tenant_id: str) -> ChatSession | None:
        sid, tid = str(session_id or "").strip(), str(tenant_id)
        if not sid:
            return None
        with self._engine.connect() as conn:
            row = conn.execute(
                select(
                    chat_session.c.id,
                    chat_session.c.title,
                    chat_session.c.created_at,
                    chat_session.c.last_message_at,
                )
                .select_from(
                    chat_session.join(
                        ui_session_owner,
                        ui_session_owner.c.session_id == chat_session.c.id,
                    )
                )
                .where(
                    chat_session.c.id == sid,
                    ui_session_owner.c.tenant_id == tid,
                )
                .limit(1)
            ).mappings().first()
        return _session_from_row(row) if row else None

    def list_admin_sessions(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        search_lower: str | None,
        active_only: bool,
        active_cutoff_iso: str,
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        """Tenant-scoped admin session browser (parity with raw ``list_admin_sessions`` SQL)."""
        tid = str(tenant_id or "").strip()
        if not tid:
            return 0, []
        uid = str(user_id or "").strip() or None
        q_text = str(search_lower or "").strip().lower() or None
        lim = max(1, min(int(limit), 500))
        off = max(0, int(offset))

        msg_cnt = (
            select(func.count())
            .select_from(chat_message)
            .where(chat_message.c.session_id == chat_session.c.id)
            .scalar_subquery()
        )
        joins = chat_session.join(
            ui_session_owner,
            ui_session_owner.c.session_id == chat_session.c.id,
        ).outerjoin(
            app_user,
            (app_user.c.tenant_id == ui_session_owner.c.tenant_id)
            & (app_user.c.id == ui_session_owner.c.user_id),
        )
        conds: list[Any] = [ui_session_owner.c.tenant_id == tid]
        if uid:
            conds.append(ui_session_owner.c.user_id == uid)
        if q_text:
            like = f"%{q_text}%"
            conds.append(
                or_(
                    func.lower(func.coalesce(app_user.c.username, literal(""))).like(like),
                    func.lower(func.coalesce(app_user.c.display_name, literal(""))).like(like),
                    func.lower(func.coalesce(chat_session.c.title, literal(""))).like(like),
                )
            )
        if active_only:
            conds.append(
                func.coalesce(chat_session.c.last_message_at, chat_session.c.created_at) >= active_cutoff_iso
            )
        wh = and_(*conds)

        data_stmt = (
            select(
                chat_session.c.id.label("session_id"),
                chat_session.c.title,
                chat_session.c.created_at,
                chat_session.c.last_message_at,
                ui_session_owner.c.user_id,
                func.coalesce(app_user.c.username, literal("")).label("username"),
                func.coalesce(app_user.c.display_name, literal("")).label("display_name"),
                msg_cnt.label("message_count"),
            )
            .select_from(joins)
            .where(wh)
            .order_by(
                func.coalesce(chat_session.c.last_message_at, chat_session.c.created_at).desc(),
                chat_session.c.created_at.desc(),
            )
            .limit(lim)
            .offset(off)
        )
        cnt_stmt = select(func.count()).select_from(joins).where(wh)

        with self._engine.connect() as conn:
            total = int(conn.execute(cnt_stmt).scalar_one() or 0)
            rows = conn.execute(data_stmt).mappings().all()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "session_id": str(r["session_id"] or ""),
                    "title": str(r["title"] or ""),
                    "created_at": str(r["created_at"] or ""),
                    "last_message_at": str(r["last_message_at"] or ""),
                    "user_id": str(r["user_id"] or ""),
                    "username": str(r["username"] or ""),
                    "display_name": str(r["display_name"] or ""),
                    "message_count": int(r["message_count"] or 0),
                }
            )
        return total, out

    def rename_chat_session(self, *, session_id: str, title: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                update(chat_session)
                .where(chat_session.c.id == str(session_id))
                .values(title=str(title))
            )

    def delete_chat_session_by_id(self, *, session_id: str) -> None:
        sid = str(session_id)
        with self._engine.begin() as conn:
            conn.execute(delete(chat_session).where(chat_session.c.id == sid))

    def try_delete_chat_session_for_administrator_username(
        self, *, session_id: str, username: str
    ) -> bool:
        sid = str(session_id or "").strip()
        if not sid:
            return False
        pred = self._administrator_username_predicate(username)
        with self._engine.begin() as conn:
            chk = conn.execute(
                select(1)
                .select_from(
                    chat_session.join(
                        ui_session_owner,
                        ui_session_owner.c.session_id == chat_session.c.id,
                    ).join(
                        app_user,
                        and_(
                            app_user.c.id == ui_session_owner.c.user_id,
                            app_user.c.tenant_id == ui_session_owner.c.tenant_id,
                        ),
                    )
                )
                .where(chat_session.c.id == sid, pred)
                .limit(1)
            ).first()
            if not chk:
                return False
            conn.execute(delete(chat_session).where(chat_session.c.id == sid))
        return True

    def try_delete_chat_session_for_tenant(self, *, session_id: str, tenant_id: str) -> bool:
        sid, tid = str(session_id or "").strip(), str(tenant_id)
        if not sid:
            return False
        with self._engine.begin() as conn:
            chk = conn.execute(
                select(1)
                .select_from(ui_session_owner)
                .where(
                    ui_session_owner.c.session_id == sid,
                    ui_session_owner.c.tenant_id == tid,
                )
                .limit(1)
            ).first()
            if not chk:
                return False
            conn.execute(delete(chat_session).where(chat_session.c.id == sid))
        return True

    def try_delete_chat_session_for_user(
        self, *, session_id: str, tenant_id: str, user_id: str
    ) -> bool:
        sid = str(session_id or "").strip()
        if not sid:
            return False
        tid, uid = str(tenant_id), str(user_id)
        with self._engine.begin() as conn:
            chk = conn.execute(
                select(1)
                .select_from(ui_session_owner)
                .where(
                    ui_session_owner.c.session_id == sid,
                    ui_session_owner.c.tenant_id == tid,
                    ui_session_owner.c.user_id == uid,
                )
                .limit(1)
            ).first()
            if not chk:
                return False
            conn.execute(delete(chat_session).where(chat_session.c.id == sid))
        return True


__all__ = ["ChatSessionsSaRepository"]
