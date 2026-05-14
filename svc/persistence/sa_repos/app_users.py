"""app_user CRUD slices via SQLAlchemy Core."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import case, delete, exists, func, insert, literal, or_, select, union, update
from sqlalchemy.engine import Engine

from svc.persistence.db.tables import app_user, channel_identity, channel_identity_v2


def _user_row_to_public_dict(r: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": r["id"],
        "tenant_id": r["tenant_id"],
        "username": r["username"],
        "display_name": r["display_name"],
        "role": r["role"],
        "is_active": bool(int(r["is_active"] or 0)),
        "created_at": r["created_at"],
        "password_hash": r["password_hash"],
        "avatar_attachment_id": str(r["avatar_attachment_id"] or "").strip() or None,
    }


class AppUsersSaRepository:
    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def count_by_tenant_username(self, *, tenant_id: str, username: str) -> int:
        tid, un = str(tenant_id), str(username)
        with self._engine.connect() as conn:
            n = conn.execute(
                select(func.count())
                .select_from(app_user)
                .where(app_user.c.tenant_id == tid, app_user.c.username == un)
            ).scalar_one()
        return int(n or 0)

    def insert_user(
        self,
        *,
        user_id: str,
        tenant_id: str,
        username: str,
        display_name: str,
        role: str,
        password_hash: str,
        is_active: int,
        created_at: str,
        avatar_attachment_id: str | None = None,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(app_user).values(
                    id=str(user_id),
                    tenant_id=str(tenant_id),
                    username=str(username),
                    display_name=str(display_name),
                    role=str(role),
                    password_hash=str(password_hash or ""),
                    is_active=int(is_active),
                    created_at=str(created_at),
                    avatar_attachment_id=avatar_attachment_id,
                )
            )

    def _select_user_columns(self):
        return select(
            app_user.c.id,
            app_user.c.tenant_id,
            app_user.c.username,
            app_user.c.display_name,
            app_user.c.role,
            func.coalesce(app_user.c.is_active, literal(1)).label("is_active"),
            app_user.c.created_at,
            func.coalesce(app_user.c.password_hash, literal("")).label("password_hash"),
            func.coalesce(app_user.c.avatar_attachment_id, literal("")).label("avatar_attachment_id"),
        )

    def fetch_by_tenant_and_id(self, *, tenant_id: str, user_id: str) -> dict[str, Any] | None:
        tid, uid = str(tenant_id), str(user_id)
        stmt = self._select_user_columns().where(app_user.c.tenant_id == tid, app_user.c.id == uid).limit(1)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _user_row_to_public_dict(row) if row else None

    def fetch_by_tenant_and_username(self, *, tenant_id: str, username: str) -> dict[str, Any] | None:
        tid, un = str(tenant_id), str(username)
        stmt = (
            self._select_user_columns()
            .where(app_user.c.tenant_id == tid, app_user.c.username == un)
            .limit(1)
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _user_row_to_public_dict(row) if row else None

    def fetch_first_by_username_global(self, *, username: str) -> dict[str, Any] | None:
        un = str(username)
        stmt = (
            self._select_user_columns()
            .where(app_user.c.username == un)
            .order_by(app_user.c.created_at.asc())
            .limit(1)
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _user_row_to_public_dict(row) if row else None

    def list_users_for_tenant(
        self,
        *,
        tenant_id: str,
        limit: int,
        offset: int,
        q: str | None,
        include_inactive: bool,
    ) -> list[dict[str, Any]]:
        tid = str(tenant_id)
        lim = max(1, int(limit))
        off = max(0, int(offset))

        has_password = case(
            (func.trim(func.coalesce(app_user.c.password_hash, literal(""))) != literal(""), 1),
            else_=0,
        ).label("has_password")

        wecom_linked = or_(
            exists(
                select(literal(1))
                .select_from(channel_identity_v2)
                .where(
                    channel_identity_v2.c.tenant_id == app_user.c.tenant_id,
                    channel_identity_v2.c.user_id == app_user.c.id,
                    channel_identity_v2.c.channel == literal("wecom"),
                )
            ),
            exists(
                select(literal(1))
                .select_from(channel_identity)
                .where(
                    channel_identity.c.tenant_id == app_user.c.tenant_id,
                    channel_identity.c.user_id == app_user.c.id,
                    channel_identity.c.channel == literal("wecom"),
                )
            ),
        ).label("wecom_linked")

        channel_linked = or_(
            exists(
                select(literal(1))
                .select_from(channel_identity_v2)
                .where(
                    channel_identity_v2.c.tenant_id == app_user.c.tenant_id,
                    channel_identity_v2.c.user_id == app_user.c.id,
                )
            ),
            exists(
                select(literal(1))
                .select_from(channel_identity)
                .where(
                    channel_identity.c.tenant_id == app_user.c.tenant_id,
                    channel_identity.c.user_id == app_user.c.id,
                )
            ),
        ).label("channel_linked")

        eid_ci = func.trim(func.coalesce(channel_identity.c.external_user_id, literal("")))
        sq1 = (
            select(eid_ci.label("eid"))
            .where(
                channel_identity.c.tenant_id == app_user.c.tenant_id,
                channel_identity.c.user_id == app_user.c.id,
                channel_identity.c.channel == literal("wecom"),
                eid_ci != literal(""),
            )
            .distinct()
        )
        eid_v2 = func.trim(func.coalesce(channel_identity_v2.c.external_user_id, literal("")))
        sq2 = (
            select(eid_v2.label("eid"))
            .where(
                channel_identity_v2.c.tenant_id == app_user.c.tenant_id,
                channel_identity_v2.c.user_id == app_user.c.id,
                channel_identity_v2.c.channel == literal("wecom"),
                eid_v2 != literal(""),
            )
            .distinct()
        )
        u_sub = union(sq1, sq2).subquery()
        if self._engine.dialect.name == "postgresql":
            wecom_ids_expr = select(func.string_agg(u_sub.c.eid, literal(", "))).scalar_subquery()
        else:
            wecom_ids_expr = select(func.group_concat(u_sub.c.eid, literal(", "))).scalar_subquery()

        stmt = (
            select(
                app_user.c.id,
                app_user.c.tenant_id,
                app_user.c.username,
                app_user.c.display_name,
                app_user.c.role,
                func.coalesce(app_user.c.is_active, literal(1)).label("is_active"),
                app_user.c.created_at,
                has_password,
                wecom_linked,
                channel_linked,
                wecom_ids_expr.label("wecom_external_user_ids"),
            )
            .where(app_user.c.tenant_id == tid)
        )
        token = str(q or "").strip()
        if token:
            key = f"%{token.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(app_user.c.display_name).like(key),
                    func.lower(func.coalesce(app_user.c.username, literal(""))).like(key),
                    app_user.c.id.like(f"%{token[:32]}%"),
                )
            )
        if not include_inactive:
            stmt = stmt.where(func.coalesce(app_user.c.is_active, literal(1)) == literal(1))
        stmt = stmt.order_by(app_user.c.created_at.desc()).limit(lim).offset(off)

        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        out: list[dict[str, Any]] = []
        for r in rows:
            has_pw = bool(int(r["has_password"] or 0))
            uname = str(r["username"] or "")
            can_chat = bool(has_pw)
            wl = r["wecom_linked"]
            cl = r["channel_linked"]
            out.append(
                {
                    "id": r["id"],
                    "tenant_id": r["tenant_id"],
                    "username": r["username"],
                    "display_name": r["display_name"],
                    "role": r["role"],
                    "is_active": bool(int(r["is_active"] or 0)),
                    "created_at": r["created_at"],
                    "has_password": has_pw,
                    "wecom_linked": bool(int(wl or 0)),
                    "channel_linked": bool(int(cl or 0)),
                    "can_chat_login": can_chat,
                    "wecom_external_user_ids": str(r["wecom_external_user_ids"] or "").strip(),
                }
            )
        return out

    def update_user_account(
        self,
        *,
        tenant_id: str,
        user_id: str,
        display_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        password_hash: str | None = None,
        avatar_attachment_id: str | None = None,
    ) -> bool:
        tid, uid = str(tenant_id), str(user_id)
        vals: dict[str, Any] = {}
        if display_name is not None:
            vals["display_name"] = str(display_name).strip() or "User"
        if role is not None:
            vals["role"] = str(role).strip() or "member"
        if is_active is not None:
            vals["is_active"] = 1 if is_active else 0
        if password_hash is not None:
            vals["password_hash"] = str(password_hash)
        if avatar_attachment_id is not None:
            aid = str(avatar_attachment_id).strip()
            vals["avatar_attachment_id"] = aid if aid else None
        if not vals:
            return False
        with self._engine.begin() as conn:
            res = conn.execute(
                update(app_user).where(app_user.c.tenant_id == tid, app_user.c.id == uid).values(**vals)
            )
            return bool(int(res.rowcount or 0) > 0)

    def delete_user_account(self, *, tenant_id: str, user_id: str) -> int:
        tid, uid = str(tenant_id), str(user_id)
        with self._engine.begin() as conn:
            res = conn.execute(delete(app_user).where(app_user.c.tenant_id == tid, app_user.c.id == uid))
            return int(res.rowcount or 0)


__all__ = ["AppUsersSaRepository"]
