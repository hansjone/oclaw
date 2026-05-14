"""ui_session_owner upserts + backfills via SQLAlchemy Core."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import and_, exists, func, insert, literal, select
from sqlalchemy.engine import Engine

from svc.persistence.db.tables import (
    channel_identity_v2,
    channel_session_v2,
    chat_session,
    ui_session_owner,
)


class UiSessionOwnerSaRepository:
    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def upsert_replace(
        self, *, session_id: str, tenant_id: str, user_id: str, created_at: str
    ) -> None:
        sid = str(session_id or "").strip()
        vals = {
            "session_id": sid,
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "created_at": str(created_at),
        }
        dialect = self._engine.dialect.name
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        else:
            from sqlalchemy.dialects.postgresql import insert as dialect_insert

        ins = dialect_insert(ui_session_owner).values(**vals)
        stmt = ins.on_conflict_do_update(
            index_elements=[ui_session_owner.c.session_id],
            set_={
                "tenant_id": ins.excluded.tenant_id,
                "user_id": ins.excluded.user_id,
                "created_at": ins.excluded.created_at,
            },
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def insert_ignore(
        self, *, session_id: str, tenant_id: str, user_id: str, created_at: str
    ) -> None:
        sid = str(session_id or "").strip()
        vals = {
            "session_id": sid,
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "created_at": str(created_at),
        }
        dialect = self._engine.dialect.name
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        else:
            from sqlalchemy.dialects.postgresql import insert as dialect_insert

        ins = dialect_insert(ui_session_owner).values(**vals)
        stmt = ins.on_conflict_do_nothing(index_elements=[ui_session_owner.c.session_id])
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def fetch_by_session_id(self, *, session_id: str) -> Mapping[str, Any] | None:
        sid = str(session_id or "").strip()
        if not sid:
            return None
        stmt = (
            select(
                ui_session_owner.c.tenant_id,
                ui_session_owner.c.user_id,
                ui_session_owner.c.created_at,
            )
            .where(ui_session_owner.c.session_id == sid)
            .limit(1)
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return row

    def backfill_orphan_sessions_for_user(
        self, *, tenant_id: str, user_id: str, default_created_at: str
    ) -> int:
        tid = str(tenant_id)
        uid = str(user_id)
        ts = str(default_created_at)
        owned = exists(
            select(1).select_from(ui_session_owner).where(ui_session_owner.c.session_id == chat_session.c.id)
        )
        sel = (
            select(
                chat_session.c.id.label("session_id"),
                literal(tid).label("tenant_id"),
                literal(uid).label("user_id"),
                func.coalesce(chat_session.c.created_at, literal(ts)).label("created_at"),
            )
            .where(~owned)
        )
        dialect = self._engine.dialect.name
        with self._engine.begin() as conn:
            if dialect == "sqlite":
                stmt = insert(ui_session_owner).prefix_with("OR IGNORE").from_select(
                    [
                        ui_session_owner.c.session_id,
                        ui_session_owner.c.tenant_id,
                        ui_session_owner.c.user_id,
                        ui_session_owner.c.created_at,
                    ],
                    sel,
                )
            else:
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = (
                    pg_insert(ui_session_owner)
                    .from_select(
                        [
                            ui_session_owner.c.session_id,
                            ui_session_owner.c.tenant_id,
                            ui_session_owner.c.user_id,
                            ui_session_owner.c.created_at,
                        ],
                        sel,
                    )
                    .on_conflict_do_nothing(index_elements=[ui_session_owner.c.session_id])
                )
            res = conn.execute(stmt)
            return int(res.rowcount or 0)

    def backfill_from_channel_v2(self, *, created_at: str) -> int:
        ts = str(created_at)
        join_on = and_(
            channel_identity_v2.c.tenant_id == channel_session_v2.c.tenant_id,
            channel_identity_v2.c.channel == channel_session_v2.c.channel,
            channel_identity_v2.c.account_id == channel_session_v2.c.account_id,
            channel_identity_v2.c.external_user_id == channel_session_v2.c.external_user_id,
        )
        sel = (
            select(
                channel_session_v2.c.session_id,
                channel_session_v2.c.tenant_id,
                channel_identity_v2.c.user_id,
                literal(ts).label("created_at"),
            )
            .distinct()
            .select_from(channel_session_v2.join(channel_identity_v2, join_on))
            .where(
                channel_session_v2.c.session_id.isnot(None),
                channel_session_v2.c.session_id != "",
            )
        )
        dialect = self._engine.dialect.name
        with self._engine.begin() as conn:
            if dialect == "sqlite":
                stmt = insert(ui_session_owner).prefix_with("OR IGNORE").from_select(
                    [
                        ui_session_owner.c.session_id,
                        ui_session_owner.c.tenant_id,
                        ui_session_owner.c.user_id,
                        ui_session_owner.c.created_at,
                    ],
                    sel,
                )
            else:
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = (
                    pg_insert(ui_session_owner)
                    .from_select(
                        [
                            ui_session_owner.c.session_id,
                            ui_session_owner.c.tenant_id,
                            ui_session_owner.c.user_id,
                            ui_session_owner.c.created_at,
                        ],
                        sel,
                    )
                    .on_conflict_do_nothing(index_elements=[ui_session_owner.c.session_id])
                )
            res = conn.execute(stmt)
            return int(res.rowcount or 0)


__all__ = ["UiSessionOwnerSaRepository"]
