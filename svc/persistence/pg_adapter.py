"""psycopg connection surface compatible with sqlite3 usage in SqliteStore."""

from __future__ import annotations

from typing import Any, Iterable, Sequence

import psycopg
from psycopg.rows import dict_row

from svc.persistence.pg_compat import adapt_sql_for_postgres


def normalize_psycopg_conninfo(url: str) -> str:
    """Strip SQLAlchemy driver suffix so :func:`psycopg.connect` accepts the URI."""
    u = str(url or "").strip()
    for prefix in (
        "postgresql+psycopg://",
        "postgresql+psycopg2://",
        "postgres+psycopg://",
        "postgres+psycopg2://",
    ):
        if u.startswith(prefix):
            rest = u.split("://", 1)[1]
            return "postgresql://" + rest
    return u


class PgCursorShim:
    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def fetchone(self) -> Any:
        return self._raw.fetchone()

    def fetchall(self) -> list[Any]:
        return self._raw.fetchall()

    @property
    def lastrowid(self) -> int:
        return 0

    @property
    def rowcount(self) -> int:
        return int(self._raw.rowcount or 0)

    def __iter__(self) -> Iterable[Any]:
        return iter(self._raw)


class PgConnShim:
    def __init__(self, raw: psycopg.Connection) -> None:
        self._raw = raw

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> PgCursorShim:
        adapted = adapt_sql_for_postgres(sql)
        cur = self._raw.execute(adapted, params or ())
        return PgCursorShim(cur)

    def executemany(self, sql: str, seq_of_params: Sequence[Sequence[Any]]) -> None:
        adapted = adapt_sql_for_postgres(sql)
        self._raw.executemany(adapted, seq_of_params)


def connect_postgres(url: str) -> psycopg.Connection:
    return psycopg.connect(normalize_psycopg_conninfo(url), row_factory=dict_row)


__all__ = ["PgConnShim", "PgCursorShim", "connect_postgres", "normalize_psycopg_conninfo"]
