"""Tests for SQLite→PostgreSQL assistant migration ordering (no live PG required)."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_MIGRATE_PATH = ROOT / "runtime" / "operations" / "scripts" / "migrate_assistant_sqlite_to_postgresql.py"


def _load_migrate_module():
    spec = importlib.util.spec_from_file_location("migrate_assistant_sqlite_to_postgresql", _MIGRATE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mig():
    return _load_migrate_module()


def test_migration_order_respects_foreign_keys(mig, tmp_path) -> None:
    db = tmp_path / "fk.sqlite"
    sl = sqlite3.connect(str(db))
    sl.executescript(
        """
        CREATE TABLE tenant(id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE app_user(
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES tenant(id),
            display_name TEXT NOT NULL
        );
        CREATE TABLE auth_session(
            session_token_hash TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES tenant(id),
            user_id TEXT NOT NULL REFERENCES app_user(id),
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );
        """
    )
    tables = mig._sqlite_user_tables(sl)
    order = mig._migration_order(sl, [t for t in tables if t in ("tenant", "app_user", "auth_session")])
    sl.close()
    assert order.index("tenant") < order.index("app_user")
    assert order.index("app_user") < order.index("auth_session")


def test_topological_sort_detects_cycle(mig) -> None:
    with pytest.raises(SystemExit, match="foreign-key-safe"):
        mig._topological_sort(["a", "b"], {"a": {"b"}, "b": {"a"}})


def test_require_ident_rejects_injection(mig) -> None:
    with pytest.raises(ValueError):
        mig._require_ident("app_user;drop")


def test_sqlite_pg_nonempty_import_conflict_msg(mig) -> None:
    assert mig._sqlite_pg_nonempty_import_conflict_msg("t", 0, 3) is None
    assert mig._sqlite_pg_nonempty_import_conflict_msg("t", 2, 0) is None
    assert mig._sqlite_pg_nonempty_import_conflict_msg("t", 0, 0) is None
    m = mig._sqlite_pg_nonempty_import_conflict_msg("llm_profile", 1, 2)
    assert m is not None
    assert "llm_profile" in m
    assert "1" in m and "2" in m


def test_pg_url_from_environ_order(monkeypatch: pytest.MonkeyPatch, mig) -> None:
    for k in (
        "AIA_ASSISTANT_DATABASE_URL",
        "OPS_ASSISTANT_DATABASE_URL",
        "AIA_ASSISTANT_PG_DSN",
        "OPS_ASSISTANT_PG_DSN",
    ):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OPS_ASSISTANT_PG_DSN", "postgresql://ops/pg")
    assert mig._pg_url_from_environ() == "postgresql://ops/pg"
    monkeypatch.setenv("AIA_ASSISTANT_PG_DSN", "postgresql://aia/pg")
    assert mig._pg_url_from_environ() == "postgresql://aia/pg"
    monkeypatch.setenv("OPS_ASSISTANT_DATABASE_URL", "postgresql://ops/db")
    assert mig._pg_url_from_environ() == "postgresql://ops/db"
    monkeypatch.setenv("AIA_ASSISTANT_DATABASE_URL", "postgresql://aia/db")
    assert mig._pg_url_from_environ() == "postgresql://aia/db"
