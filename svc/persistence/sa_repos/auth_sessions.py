"""auth_session access via SQLAlchemy Core (SQLite + PostgreSQL)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine

from svc.persistence.db.tables import auth_session


class AuthSessionsSaRepository:
    """Phase-2 SA migration: admin login session rows."""

    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def insert_session(
        self,
        *,
        session_token_hash: str,
        tenant_id: str,
        user_id: str,
        role: str,
        created_at: str,
        expires_at: str,
        last_seen_at: str,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(auth_session).values(
                    session_token_hash=str(session_token_hash),
                    tenant_id=str(tenant_id),
                    user_id=str(user_id),
                    role=str(role),
                    created_at=str(created_at),
                    expires_at=str(expires_at),
                    last_seen_at=str(last_seen_at),
                    revoked_at=None,
                )
            )

    def revoke_one(self, *, session_token_hash: str, revoked_at: str) -> int:
        with self._engine.begin() as conn:
            res = conn.execute(
                update(auth_session)
                .where(
                    auth_session.c.session_token_hash == str(session_token_hash),
                    auth_session.c.revoked_at.is_(None),
                )
                .values(revoked_at=str(revoked_at))
            )
            n = res.rowcount
        if n is None or n < 0:
            return 0
        return int(n)

    def revoke_all_active(self, *, revoked_at: str) -> int:
        with self._engine.begin() as conn:
            res = conn.execute(
                update(auth_session)
                .where(auth_session.c.revoked_at.is_(None))
                .values(revoked_at=str(revoked_at))
            )
            n = res.rowcount
        if n is None or n < 0:
            return 0
        return int(n)

    def fetch_by_hash(self, *, session_token_hash: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(
                    auth_session.c.session_token_hash,
                    auth_session.c.tenant_id,
                    auth_session.c.user_id,
                    auth_session.c.role,
                    auth_session.c.created_at,
                    auth_session.c.expires_at,
                    auth_session.c.last_seen_at,
                    auth_session.c.revoked_at,
                )
                .where(auth_session.c.session_token_hash == str(session_token_hash))
                .limit(1)
            ).mappings().first()
        if row is None:
            return None
        return dict(row)

    def touch(self, *, session_token_hash: str, last_seen_at: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                update(auth_session)
                .where(auth_session.c.session_token_hash == str(session_token_hash))
                .values(last_seen_at=str(last_seen_at))
            )


__all__ = ["AuthSessionsSaRepository"]
