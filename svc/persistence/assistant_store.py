"""Single entry point for the assistant persistence layer (SQLite or PostgreSQL)."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from svc.config.database import (
    assistant_db_backend,
    assistant_postgres_dsn,
    assistant_sqlalchemy_url,
)
from svc.persistence.assistant_store_protocol import AssistantStoreProtocol

_singleton: AssistantStoreProtocol | None = None
_singleton_key: str | None = None
_lock = threading.Lock()


def reset_assistant_store_singleton() -> None:
    """Drop the cached :func:`get_assistant_store` instance (tests / engine URL changes)."""
    global _singleton, _singleton_key
    _singleton = None
    _singleton_key = None


def get_assistant_store() -> AssistantStoreProtocol:
    """Return the process-wide assistant store implementation.

    - Default: SQLite at :func:`svc.config.paths.db_path`.
    - ``AIA_ASSISTANT_DB_BACKEND=postgresql`` + DSN: same :class:`~svc.persistence.sqlite_store.SqliteStore`
      API over PostgreSQL (schema via Alembic / ``postgresql_bootstrap.sql``).

    The store is **cached per process** for a stable (backend, connection key) so ``SqliteStore.__init__``
    does not re-run PostgreSQL bootstrap / orphan pruning on every HTTP or WS call (which could race
    with in-flight writes and make messages disappear after tool rounds).

    The cache key for PostgreSQL uses a **hash of the SQLAlchemy URL** (not the raw DSN string) so logs
    and debug dumps are less likely to embed credentials.

    When the effective key changes (e.g. tests switch ``AIA_ASSISTANT_DB_PATH`` or DSN), the SQLAlchemy
    engine cache is cleared so pooled connections are not reused for the wrong database.

    Tests should keep constructing ``SqliteStore(path)`` with an explicit file path; production code
    should prefer this factory for ``db_path()``-backed instances.

    Return type is :class:`~svc.persistence.assistant_store_protocol.AssistantStoreProtocol`; the
    concrete class is :class:`~svc.persistence.sqlite_store.SqliteStore` for both backends.
    """
    global _singleton, _singleton_key
    from svc.config.paths import db_path
    from svc.persistence.sqlite_store import SqliteStore

    if assistant_db_backend() == "postgresql":
        key = f"postgresql::{hashlib.sha256(assistant_sqlalchemy_url().encode()).hexdigest()}"
    else:
        key = f"sqlite::{Path(db_path()).resolve()}"

    inst = _singleton
    if inst is not None and _singleton_key == key:
        return inst

    with _lock:
        if _singleton is not None and _singleton_key == key:
            return _singleton
        if _singleton_key is not None and _singleton_key != key:
            from svc.persistence.db.engine import clear_assistant_engine_cache

            clear_assistant_engine_cache()
        if assistant_db_backend() == "postgresql":
            _singleton = SqliteStore(None, postgres_url=assistant_postgres_dsn())
        else:
            _singleton = SqliteStore(db_path())
        _singleton_key = key
        return _singleton


__all__ = ["get_assistant_store", "reset_assistant_store_singleton"]
