"""Assistant database backend selection (SQLite default, PostgreSQL opt-in via env)."""

from __future__ import annotations

import os
import warnings

_PG_URL_IGNORED_WARNED = False


def assistant_db_backend() -> str:
    """Return ``sqlite`` (default) or ``postgresql``."""
    raw = (
        os.getenv("AIA_ASSISTANT_DB_BACKEND")
        or os.getenv("OPS_ASSISTANT_DB_BACKEND")
        or "sqlite"
    ).strip().lower()
    if raw in ("sqlite", ""):
        return "sqlite"
    if raw in ("pg", "postgres", "postgresql"):
        return "postgresql"
    raise ValueError(
        f"Invalid assistant DB backend {raw!r}. "
        "Use sqlite (default) or postgresql (aliases: pg, postgres)."
    )


def _warn_if_postgres_url_ignored_for_sqlite() -> None:
    """Emit once if PostgreSQL DSN env vars are set but backend is still SQLite."""
    global _PG_URL_IGNORED_WARNED
    if _PG_URL_IGNORED_WARNED or assistant_db_backend() != "sqlite":
        return
    for var in (
        "AIA_ASSISTANT_DATABASE_URL",
        "OPS_ASSISTANT_DATABASE_URL",
        "AIA_ASSISTANT_PG_DSN",
        "OPS_ASSISTANT_PG_DSN",
    ):
        if str(os.getenv(var) or "").strip():
            _PG_URL_IGNORED_WARNED = True
            warnings.warn(
                f"{var} is set but assistant DB backend is sqlite; the PostgreSQL URL is ignored. "
                "Set AIA_ASSISTANT_DB_BACKEND=postgresql (or pg/postgres) to use PostgreSQL.",
                UserWarning,
                stacklevel=2,
            )
            return


def assistant_sqlalchemy_url() -> str:
    """SQLAlchemy URL for the assistant store (sqlite or postgresql+psycopg)."""
    _warn_if_postgres_url_ignored_for_sqlite()
    if assistant_db_backend() == "postgresql":
        raw = assistant_postgres_dsn()
        if raw.startswith("postgresql+") or raw.startswith("postgres+"):
            return raw
        if raw.startswith("postgresql://") or raw.startswith("postgres://"):
            return "postgresql+psycopg://" + raw.split("://", 1)[1]
        return raw
    from svc.config.paths import db_path

    p = db_path().replace("\\", "/")
    return f"sqlite+pysqlite:///{p}"


def assistant_postgres_dsn() -> str:
    """PostgreSQL connection URI for the assistant store (psycopg/libpq format)."""
    url = (
        os.getenv("AIA_ASSISTANT_DATABASE_URL")
        or os.getenv("OPS_ASSISTANT_DATABASE_URL")
        or os.getenv("AIA_ASSISTANT_PG_DSN")
        or os.getenv("OPS_ASSISTANT_PG_DSN")
        or ""
    ).strip()
    if not url:
        raise ValueError(
            "PostgreSQL backend requires AIA_ASSISTANT_DATABASE_URL (or OPS_ASSISTANT_DATABASE_URL) "
            "to a libpq connection string, e.g. postgresql://user:pass@127.0.0.1:5432/oclaw"
        )
    return url


def reset_assistant_db_config_warnings_for_tests() -> None:
    """Reset one-shot warnings (pytest only)."""
    global _PG_URL_IGNORED_WARNED
    _PG_URL_IGNORED_WARNED = False


__all__ = [
    "assistant_db_backend",
    "assistant_postgres_dsn",
    "assistant_sqlalchemy_url",
    "reset_assistant_db_config_warnings_for_tests",
]
