"""Guardrails for SQLite→PostgreSQL SQL rewriting used by SqliteStore."""

from __future__ import annotations

from svc.persistence import pg_compat
from svc.persistence.pg_adapter import normalize_psycopg_conninfo


def test_normalize_psycopg_conninfo_strips_sqlalchemy_driver() -> None:
    u = "postgresql+psycopg://user:pass@127.0.0.1:5432/oclaw"
    assert normalize_psycopg_conninfo(u) == "postgresql://user:pass@127.0.0.1:5432/oclaw"


def test_insert_or_replace_ui_session_owner_rewritten() -> None:
    sql = """INSERT OR REPLACE INTO ui_session_owner(session_id, tenant_id, user_id, created_at)
                VALUES (?, ?, ?, ?)"""
    adapted = pg_compat.adapt_sql_for_postgres(sql)
    assert "INSERT OR REPLACE" not in adapted.upper()
    assert "ON CONFLICT" in adapted.upper()


def test_llm_profile_insert_or_ignore_rewritten() -> None:
    sql = """INSERT OR IGNORE INTO llm_profile
                (id, name, mode, model, base_url, api_key, updated_at, is_builtin, hide_in_ui, owner_user_id)
            VALUES (?, ?, 'ollama', ?, ?, NULL, ?, 1, 0, NULL)"""
    adapted = pg_compat.adapt_sql_for_postgres(sql)
    assert "INSERT OR IGNORE" not in adapted.upper()
    assert "ON CONFLICT (id) DO NOTHING" in adapted


def test_role_permission_insert_or_ignore_rewritten() -> None:
    sql = """INSERT OR IGNORE INTO role_permission(role, permission, created_at)
                    VALUES (?, ?, ?)"""
    adapted = pg_compat.adapt_sql_for_postgres(sql)
    assert "INSERT OR IGNORE" not in adapted.upper()
    assert "ON CONFLICT (role, permission) DO NOTHING" in adapted


def test_scrub_nul_bytes_from_text() -> None:
    assert pg_compat.scrub_nul_bytes_from_text(None) is None
    assert pg_compat.scrub_nul_bytes_from_text("ok") == "ok"
    assert pg_compat.scrub_nul_bytes_from_text("a\x00b") == "ab"


def test_scrub_nul_bytes_from_jsonable_nested() -> None:
    assert pg_compat.scrub_nul_bytes_from_jsonable({"x": "y\x00z"}) == {"x": "yz"}


def test_escape_percent_in_sql_literals_for_like_b64_prefix() -> None:
    sql = "SELECT 1 FROM llm_profile WHERE api_key LIKE 'b64:%'"
    adapted = pg_compat.adapt_sql_for_postgres(sql)
    assert "LIKE 'b64:%%'" in adapted
