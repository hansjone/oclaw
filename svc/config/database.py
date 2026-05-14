"""Assistant database backend selection (SQLite default, PostgreSQL opt-in via env)."""

from __future__ import annotations

import os


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


def assistant_sqlalchemy_url() -> str:
    """SQLAlchemy URL for the assistant store (sqlite or postgresql+psycopg)."""
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


__all__ = ["assistant_db_backend", "assistant_postgres_dsn", "assistant_sqlalchemy_url"]
