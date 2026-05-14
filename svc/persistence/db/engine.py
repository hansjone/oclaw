"""SQLAlchemy Engine factory for assistant DB (SQLite or PostgreSQL)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from svc.config.database import assistant_sqlalchemy_url


def _sqlite_sa_url_from_os_path(path: str) -> str:
    """Build the same ``sqlite+pysqlite:///...`` URL shape as :func:`svc.config.database.assistant_sqlalchemy_url`."""
    p = Path(path).resolve().as_posix()
    return f"sqlite+pysqlite:///{p}"


def _register_sqlite_pragmas(eng: Engine) -> None:
    @event.listens_for(eng, "connect")
    def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON;")
        cur.execute("PRAGMA journal_mode = WAL;")
        cur.execute("PRAGMA synchronous = NORMAL;")
        cur.execute("PRAGMA busy_timeout = 30000;")
        cur.close()


@lru_cache(maxsize=64)
def _engine_for_url(url: str) -> Engine:
    """One engine per URL (process-wide)."""
    pool_kw: dict[str, Any] = {}
    if url.startswith("sqlite"):
        pool_kw["poolclass"] = NullPool
    else:
        pool_kw["pool_pre_ping"] = True
    eng = create_engine(url, future=True, **pool_kw)
    if url.startswith("sqlite"):
        _register_sqlite_pragmas(eng)
    return eng


def get_assistant_engine() -> Engine:
    """Engine for the current env-selected assistant DB (Alembic, ``get_assistant_store`` SQLite path)."""
    return _engine_for_url(assistant_sqlalchemy_url())


def engine_for_sqlite_file(path: str) -> Engine:
    """Engine for a specific SQLite file (e.g. ``SqliteStore('/tmp/x.sqlite')`` without env ``DB_PATH``)."""
    return _engine_for_url(_sqlite_sa_url_from_os_path(path))


def clear_assistant_engine_cache() -> None:
    """Drop cached engines (e.g. tests that delete temp DB files must call this before removing the directory)."""
    _engine_for_url.cache_clear()
    try:
        from svc.persistence.assistant_store import reset_assistant_store_singleton

        reset_assistant_store_singleton()
    except Exception:
        pass


__all__ = [
    "clear_assistant_engine_cache",
    "engine_for_sqlite_file",
    "get_assistant_engine",
]
