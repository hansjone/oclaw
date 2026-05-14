"""Initial PostgreSQL schema for assistant store (from SQLite parity DDL)."""

from __future__ import annotations

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "001_assistant_pg_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    root = Path(__file__).resolve().parents[2]
    sql_path = root / "svc" / "persistence" / "ddl" / "postgresql_bootstrap.sql"
    raw = sql_path.read_text(encoding="utf-8")
    for part in raw.split(";"):
        stmt = part.strip()
        if not stmt or stmt.startswith("--"):
            continue
        op.execute(text(stmt))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    raise NotImplementedError("Assistant PG downgrade not supported; restore from backup.")
