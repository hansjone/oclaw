"""SQLAlchemy slice tests: app_setting repository (phase-1 migration)."""

from __future__ import annotations

import pytest

from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "sa_slice.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def test_sa_app_setting_roundtrip(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    s.set_setting("sa_k", "sa_v")
    assert s.get_setting("sa_k") == "sa_v"
    s.set_setting("sa_k", "sa_v2")
    assert s.get_setting("sa_k") == "sa_v2"
    s.delete_setting("sa_k")
    assert s.get_setting("sa_k") is None


def test_sa_app_setting_get_ignores_secret(fresh_sqlite_store: SqliteStore) -> None:
    s = fresh_sqlite_store
    s.set_secret("sec_k", "plain")
    assert s.get_setting("sec_k") is None
    assert s.get_secret("sec_k") == "plain"
    s.delete_setting("sec_k")
    assert s.get_secret("sec_k") is None
