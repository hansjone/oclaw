"""Tests for assistant DB backend selection."""

from __future__ import annotations

import os

import pytest

from svc.config import database as db_cfg
from svc.persistence import assistant_store as as_mod


def test_assistant_db_backend_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.delenv("OPS_ASSISTANT_DB_BACKEND", raising=False)
    assert db_cfg.assistant_db_backend() == "sqlite"


def test_assistant_db_backend_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    for raw in ("postgresql", "POSTGRES", "pg"):
        monkeypatch.setenv("AIA_ASSISTANT_DB_BACKEND", raw)
        assert db_cfg.assistant_db_backend() == "postgresql"
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.delenv("OPS_ASSISTANT_DB_BACKEND", raising=False)


def test_assistant_postgres_dsn_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIA_ASSISTANT_DB_BACKEND", "postgresql")
    monkeypatch.delenv("AIA_ASSISTANT_DATABASE_URL", raising=False)
    monkeypatch.delenv("OPS_ASSISTANT_DATABASE_URL", raising=False)
    monkeypatch.delenv("AIA_ASSISTANT_PG_DSN", raising=False)
    monkeypatch.delenv("OPS_ASSISTANT_PG_DSN", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        db_cfg.assistant_postgres_dsn()


def test_get_assistant_store_sqlite(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(tmp_path / "t.sqlite"))
    as_mod.reset_assistant_store_singleton()
    from svc.persistence.sqlite_store import SqliteStore

    s = as_mod.get_assistant_store()
    assert isinstance(s, SqliteStore)
    assert as_mod.get_assistant_store() is s


def test_assistant_sqlalchemy_url_sqlite(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(tmp_path / "t.sqlite"))
    u = db_cfg.assistant_sqlalchemy_url()
    assert u.startswith("sqlite+pysqlite:///")


@pytest.mark.skipif(
    not (os.getenv("AIA_TEST_PG_URL") or "").strip(),
    reason="Set AIA_TEST_PG_URL to run PostgreSQL integration test",
)
def test_get_assistant_store_postgresql_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    as_mod.reset_assistant_store_singleton()
    monkeypatch.setenv("AIA_ASSISTANT_DB_BACKEND", "postgresql")
    monkeypatch.setenv("AIA_ASSISTANT_DATABASE_URL", os.environ["AIA_TEST_PG_URL"].strip())
    from svc.persistence.sqlite_store import SqliteStore

    s = as_mod.get_assistant_store()
    assert isinstance(s, SqliteStore)
    assert s._use_pg is True
    assert s.get_setting("no_such_key_integration_test") is None
    sess = s.create_session("pg_smoke_session")
    assert sess.id
    msg = s.add_message(sess.id, "user", "pg-smoke-body")
    assert msg.id > 0
    msgs = s.get_messages(sess.id, limit=10)
    assert len(msgs) == 1
    assert msgs[0].content == "pg-smoke-body"


def test_assistant_db_backend_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIA_ASSISTANT_DB_BACKEND", "mysql")
    with pytest.raises(ValueError, match="Invalid assistant DB backend"):
        db_cfg.assistant_db_backend()
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
