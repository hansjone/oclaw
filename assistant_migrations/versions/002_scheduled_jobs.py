"""Add scheduled_job tables for PostgreSQL deployments."""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "002_scheduled_jobs"
down_revision = "001_assistant_pg_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS scheduled_job (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                schedule_kind TEXT NOT NULL,
                schedule_expr TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
                prompt_text TEXT NOT NULL,
                interaction_mode TEXT NOT NULL DEFAULT 'expert',
                specialist TEXT NOT NULL DEFAULT 'generalist',
                lang TEXT NOT NULL DEFAULT 'zh',
                delivery_json TEXT NOT NULL DEFAULT '{}',
                source_session_id TEXT,
                created_by_user_id TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'admin',
                next_run_at TEXT,
                last_run_at TEXT,
                last_run_status TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
    )
    op.execute(text("CREATE INDEX IF NOT EXISTS idx_scheduled_job_due ON scheduled_job(status, next_run_at)"))
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS scheduled_job_run (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES scheduled_job(id) ON DELETE CASCADE,
                tenant_id TEXT NOT NULL,
                status TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                session_id TEXT,
                oclaw_task_id TEXT,
                run_id TEXT,
                reply_text TEXT NOT NULL DEFAULT '',
                delivery_status_json TEXT NOT NULL DEFAULT '{}',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
    )
    op.execute(
        text("CREATE INDEX IF NOT EXISTS idx_scheduled_job_run_job ON scheduled_job_run(job_id, created_at DESC)")
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(text("DROP TABLE IF EXISTS scheduled_job_run"))
    op.execute(text("DROP TABLE IF EXISTS scheduled_job"))
