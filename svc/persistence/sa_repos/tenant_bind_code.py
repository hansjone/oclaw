"""tenant + bind_code via SQLAlchemy Core."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Engine

from svc.persistence.db.tables import bind_code, tenant


class TenantSaRepository:
    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def insert_tenant(self, *, tenant_id: str, name: str, created_at: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(tenant).values(
                    id=str(tenant_id),
                    name=str(name),
                    created_at=str(created_at),
                )
            )

    def delete_tenant(self, *, tenant_id: str) -> int:
        tid = str(tenant_id or "").strip()
        if not tid:
            return 0
        with self._engine.begin() as conn:
            res = conn.execute(delete(tenant).where(tenant.c.id == tid))
            return int(res.rowcount or 0)

    def list_tenants(self, *, limit: int) -> list[dict[str, Any]]:
        lim = max(1, int(limit))
        stmt = (
            select(tenant.c.id, tenant.c.name, tenant.c.created_at)
            .order_by(tenant.c.created_at.desc())
            .limit(lim)
        )
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings().all()]


class BindCodeSaRepository:
    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def insert_bind_code(
        self, *, code: str, tenant_id: str, role: str, created_at: str
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(bind_code).values(
                    code=str(code),
                    tenant_id=str(tenant_id),
                    role=str(role),
                    created_at=str(created_at),
                    used_at=None,
                    used_by_external_user_id=None,
                )
            )

    def fetch_by_code(self, *, code: str) -> Mapping[str, Any] | None:
        c = str(code or "").strip()
        if not c:
            return None
        stmt = (
            select(
                bind_code.c.code,
                bind_code.c.tenant_id,
                bind_code.c.role,
                bind_code.c.created_at,
                bind_code.c.used_at,
                bind_code.c.used_by_external_user_id,
            )
            .where(bind_code.c.code == c)
            .limit(1)
        )
        with self._engine.connect() as conn:
            return conn.execute(stmt).mappings().first()

    def mark_used(
        self, *, code: str, used_at: str, used_by_external_user_id: str
    ) -> None:
        c = str(code or "").strip()
        with self._engine.begin() as conn:
            conn.execute(
                update(bind_code)
                .where(bind_code.c.code == c)
                .values(used_at=str(used_at), used_by_external_user_id=str(used_by_external_user_id))
            )

    def list_bind_codes(self, *, tenant_id: str | None, limit: int) -> list[dict[str, Any]]:
        lim = max(1, int(limit))
        stmt = select(
            bind_code.c.code,
            bind_code.c.tenant_id,
            bind_code.c.role,
            bind_code.c.created_at,
            bind_code.c.used_at,
            bind_code.c.used_by_external_user_id,
        ).order_by(bind_code.c.created_at.desc())
        if tenant_id:
            stmt = stmt.where(bind_code.c.tenant_id == str(tenant_id))
        stmt = stmt.limit(lim)
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings().all()]


__all__ = ["BindCodeSaRepository", "TenantSaRepository"]
