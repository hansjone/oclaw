"""app_setting access via SQLAlchemy Core (SQLite + PostgreSQL)."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Engine

from svc.persistence.db.tables import app_setting


class AppSettingsSaRepository:
    """Phase-1 SA migration: ``app_setting`` reads/writes only."""

    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def _dialect(self, conn: Connection) -> str:
        return conn.engine.dialect.name

    def _upsert(
        self,
        conn: Connection,
        *,
        key: str,
        value: str,
        is_secret: int,
        updated_at: str,
    ) -> None:
        dialect = self._dialect(conn)
        if dialect == "sqlite":
            ins = sqlite_insert(app_setting).values(
                key=key,
                value=value,
                is_secret=is_secret,
                updated_at=updated_at,
            )
            stmt = ins.on_conflict_do_update(
                index_elements=[app_setting.c.key],
                set_={
                    "value": ins.excluded.value,
                    "is_secret": ins.excluded.is_secret,
                    "updated_at": ins.excluded.updated_at,
                },
            )
        elif dialect == "postgresql":
            ins = pg_insert(app_setting).values(
                key=key,
                value=value,
                is_secret=is_secret,
                updated_at=updated_at,
            )
            stmt = ins.on_conflict_do_update(
                index_elements=[app_setting.c.key],
                set_={
                    "value": ins.excluded.value,
                    "is_secret": ins.excluded.is_secret,
                    "updated_at": ins.excluded.updated_at,
                },
            )
        else:
            raise RuntimeError(f"unsupported SQLAlchemy dialect for app_setting: {dialect!r}")
        conn.execute(stmt)

    def upsert_plain(self, *, key: str, value: str, updated_at: str) -> None:
        with self._engine.begin() as conn:
            self._upsert(conn, key=key, value=value, is_secret=0, updated_at=updated_at)

    def upsert_secret(self, *, key: str, encoded_value: str, updated_at: str) -> None:
        with self._engine.begin() as conn:
            self._upsert(conn, key=key, value=encoded_value, is_secret=1, updated_at=updated_at)

    def fetch_row(self, *, key: str) -> tuple[str, int] | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(app_setting.c.value, app_setting.c.is_secret).where(app_setting.c.key == key)
            ).one_or_none()
        if row is None:
            return None
        return (str(row[0]), int(row[1]))

    def delete_key(self, *, key: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(delete(app_setting).where(app_setting.c.key == key))

    def migrate_b64_secrets(
        self,
        *,
        ts: str,
        decode_secret: Callable[[str], str],
        encode_secret: Callable[[str], str],
        predicate_new_encoding: Callable[[str], bool],
    ) -> int:
        """Re-encode legacy ``b64:`` rows; idempotent. Returns rows updated."""
        migrated = 0
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(app_setting.c.key, app_setting.c.value).where(
                    app_setting.c.is_secret == 1,
                    app_setting.c.value.like("b64:%"),
                )
            ).all()
            for k, v in rows:
                key = str(k or "")
                val = str(v or "")
                if not key:
                    continue
                try:
                    plain = decode_secret(val)
                except Exception:
                    continue
                enc = encode_secret(plain)
                if enc != val and predicate_new_encoding(enc):
                    conn.execute(
                        update(app_setting)
                        .where(
                            app_setting.c.key == key,
                            app_setting.c.is_secret == 1,
                        )
                        .values(value=enc, updated_at=ts)
                    )
                    migrated += 1
        return migrated

    def count_legacy_b64_secrets(self) -> int:
        with self._engine.connect() as conn:
            n = conn.execute(
                select(func.count()).select_from(app_setting).where(
                    app_setting.c.is_secret == 1,
                    app_setting.c.value.like("b64:%"),
                )
            ).scalar_one()
        return int(n or 0)


__all__ = ["AppSettingsSaRepository"]
