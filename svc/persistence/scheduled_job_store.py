from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from runtime.scheduler.expressions import compute_next_run_at, normalize_schedule_kind
from runtime.scheduler.system_timezone import default_system_timezone

SCHEDULED_JOB_DDL = """
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
    recipe_json TEXT NOT NULL DEFAULT '{}',
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
);
"""

SCHEDULED_JOB_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_scheduled_job_due
ON scheduled_job(status, next_run_at);
"""

SCHEDULED_JOB_RUN_DDL = """
CREATE TABLE IF NOT EXISTS scheduled_job_run (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
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
    created_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES scheduled_job(id) ON DELETE CASCADE
);
"""

SCHEDULED_JOB_RUN_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_scheduled_job_run_job
ON scheduled_job_run(job_id, created_at DESC);
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ScheduledJob:
    id: str
    tenant_id: str
    name: str
    description: str
    status: str
    schedule_kind: str
    schedule_expr: str
    timezone: str
    prompt_text: str
    recipe_json: str
    interaction_mode: str
    specialist: str
    lang: str
    delivery_json: str
    source_session_id: str | None
    created_by_user_id: str
    source: str
    next_run_at: str | None
    last_run_at: str | None
    last_run_status: str
    created_at: str
    updated_at: str


def _row_field(row: Any, key: str, default: str = "") -> str:
    try:
        if hasattr(row, "keys") and key in row.keys():
            return str(row[key] if row[key] is not None else default)
    except Exception:
        pass
    try:
        return str(row[key] if row[key] is not None else default)
    except Exception:
        return default


@dataclass(frozen=True)
class ScheduledJobRun:
    id: str
    job_id: str
    tenant_id: str
    status: str
    scheduled_at: str
    started_at: str | None
    finished_at: str | None
    session_id: str | None
    oclaw_task_id: str | None
    run_id: str | None
    reply_text: str
    delivery_status_json: str
    error: str
    created_at: str


def _row_to_job(row: Any) -> ScheduledJob:
    return ScheduledJob(
        id=_row_field(row, "id"),
        tenant_id=_row_field(row, "tenant_id"),
        name=_row_field(row, "name"),
        description=_row_field(row, "description"),
        status=_row_field(row, "status"),
        schedule_kind=_row_field(row, "schedule_kind"),
        schedule_expr=_row_field(row, "schedule_expr"),
        timezone=_row_field(row, "timezone", default_system_timezone()) or default_system_timezone(),
        prompt_text=_row_field(row, "prompt_text"),
        recipe_json=_row_field(row, "recipe_json", "{}") or "{}",
        interaction_mode=_row_field(row, "interaction_mode", "expert") or "expert",
        specialist=_row_field(row, "specialist", "generalist") or "generalist",
        lang=_row_field(row, "lang", "zh") or "zh",
        delivery_json=_row_field(row, "delivery_json", "{}") or "{}",
        source_session_id=_row_field(row, "source_session_id") or None,
        created_by_user_id=_row_field(row, "created_by_user_id"),
        source=_row_field(row, "source"),
        next_run_at=_row_field(row, "next_run_at") or None,
        last_run_at=_row_field(row, "last_run_at") or None,
        last_run_status=_row_field(row, "last_run_status"),
        created_at=_row_field(row, "created_at"),
        updated_at=_row_field(row, "updated_at"),
    )


def _row_to_run(row: Any) -> ScheduledJobRun:
    return ScheduledJobRun(
        id=str(row["id"] or ""),
        job_id=str(row["job_id"] or ""),
        tenant_id=str(row["tenant_id"] or ""),
        status=str(row["status"] or ""),
        scheduled_at=str(row["scheduled_at"] or ""),
        started_at=str(row["started_at"] or "") or None,
        finished_at=str(row["finished_at"] or "") or None,
        session_id=str(row["session_id"] or "") or None,
        oclaw_task_id=str(row["oclaw_task_id"] or "") or None,
        run_id=str(row["run_id"] or "") or None,
        reply_text=str(row["reply_text"] or ""),
        delivery_status_json=str(row["delivery_status_json"] or "{}"),
        error=str(row["error"] or ""),
        created_at=str(row["created_at"] or ""),
    )


_JOB_SELECT = """
SELECT id, tenant_id, name, description, status, schedule_kind, schedule_expr, timezone,
       prompt_text, recipe_json, interaction_mode, specialist, lang, delivery_json, source_session_id,
       created_by_user_id, source, next_run_at, last_run_at, last_run_status, created_at, updated_at
FROM scheduled_job
"""


class ScheduledJobStoreMixin:
    def ensure_scheduled_job_tables(self, conn: Any) -> None:
        conn.execute(SCHEDULED_JOB_DDL)
        conn.execute(SCHEDULED_JOB_INDEX_DDL)
        conn.execute(SCHEDULED_JOB_RUN_DDL)
        conn.execute(SCHEDULED_JOB_RUN_INDEX_DDL)
        self._ensure_scheduled_job_recipe_column(conn)

    def _ensure_scheduled_job_recipe_column(self, conn: Any) -> None:
        if bool(getattr(self, "_use_pg", False)):
            conn.execute(
                "ALTER TABLE scheduled_job ADD COLUMN IF NOT EXISTS recipe_json TEXT NOT NULL DEFAULT '{}'"
            )
            return
        cols = {row[1] for row in conn.execute("PRAGMA table_info(scheduled_job)").fetchall()}
        if "recipe_json" not in cols:
            conn.execute(
                "ALTER TABLE scheduled_job ADD COLUMN recipe_json TEXT NOT NULL DEFAULT '{}'"
            )

    def scheduled_job_create(
        self,
        *,
        tenant_id: str,
        name: str,
        prompt_text: str,
        schedule_kind: str,
        schedule_expr: str,
        timezone_name: str | None = None,
        description: str = "",
        interaction_mode: str = "expert",
        specialist: str = "generalist",
        lang: str = "zh",
        delivery: dict[str, Any] | None = None,
        recipe: dict[str, Any] | None = None,
        source_session_id: str | None = None,
        created_by_user_id: str = "",
        source: str = "admin",
        status: str = "active",
    ) -> ScheduledJob:
        jid = str(uuid.uuid4())
        ts = utc_now_iso()
        kind = normalize_schedule_kind(schedule_kind)
        tz = str(timezone_name or default_system_timezone()).strip() or default_system_timezone()
        next_run = compute_next_run_at(
            schedule_kind=kind,
            schedule_expr=str(schedule_expr or "").strip(),
            timezone_name=tz,
            from_dt=None,
        )
        delivery_json = json.dumps(delivery or {}, ensure_ascii=False)
        recipe_json = json.dumps(recipe or {}, ensure_ascii=False)
        with self._connect() as conn:  # type: ignore[attr-defined]
            conn.execute(
                """
                INSERT INTO scheduled_job
                    (id, tenant_id, name, description, status, schedule_kind, schedule_expr, timezone,
                     prompt_text, recipe_json, interaction_mode, specialist, lang, delivery_json, source_session_id,
                     created_by_user_id, source, next_run_at, last_run_at, last_run_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, '', ?, ?)
                """,
                (
                    jid,
                    str(tenant_id),
                    str(name or "").strip() or "Scheduled task",
                    str(description or ""),
                    str(status or "active"),
                    kind,
                    str(schedule_expr or "").strip(),
                    tz,
                    str(prompt_text or "").strip(),
                    recipe_json,
                    str(interaction_mode or "expert"),
                    str(specialist or "generalist"),
                    str(lang or "zh"),
                    delivery_json,
                    str(source_session_id) if source_session_id else None,
                    str(created_by_user_id or ""),
                    str(source or "admin"),
                    next_run,
                    ts,
                    ts,
                ),
            )
        got = self.scheduled_job_get(job_id=jid, tenant_id=tenant_id)
        if not got:
            raise RuntimeError("failed to create scheduled job")
        return got

    def scheduled_job_get(self, *, job_id: str, tenant_id: str | None = None) -> ScheduledJob | None:
        with self._connect() as conn:  # type: ignore[attr-defined]
            if tenant_id:
                row = conn.execute(
                    f"{_JOB_SELECT} WHERE id = ? AND tenant_id = ?",
                    (str(job_id), str(tenant_id)),
                ).fetchone()
            else:
                row = conn.execute(f"{_JOB_SELECT} WHERE id = ?", (str(job_id),)).fetchone()
        if not row:
            return None
        return _row_to_job(row)

    def scheduled_job_list(
        self,
        *,
        tenant_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ScheduledJob]:
        lim = max(1, min(int(limit), 500))
        off = max(0, int(offset))
        where = ["tenant_id = ?", "status != 'deleted'"]
        params: list[Any] = [str(tenant_id)]
        if status:
            where.append("status = ?")
            params.append(str(status))
        wsql = " AND ".join(where)
        with self._connect() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(
                f"{_JOB_SELECT} WHERE {wsql} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (*params, lim, off),
            ).fetchall()
        return [_row_to_job(r) for r in rows]

    def scheduled_job_update(
        self,
        *,
        tenant_id: str,
        job_id: str,
        patch: dict[str, Any],
    ) -> ScheduledJob | None:
        cur = self.scheduled_job_get(job_id=job_id, tenant_id=tenant_id)
        if not cur:
            return None
        p = dict(patch or {})
        name = str(p.get("name") if "name" in p else cur.name)
        description = str(p.get("description") if "description" in p else cur.description)
        prompt_text = str(p.get("prompt_text") if "prompt_text" in p else cur.prompt_text)
        interaction_mode = str(p.get("interaction_mode") if "interaction_mode" in p else cur.interaction_mode)
        specialist = str(p.get("specialist") if "specialist" in p else cur.specialist)
        lang = str(p.get("lang") if "lang" in p else cur.lang)
        schedule_kind = normalize_schedule_kind(
            str(p.get("schedule_kind") if "schedule_kind" in p else cur.schedule_kind)
        )
        schedule_expr = str(p.get("schedule_expr") if "schedule_expr" in p else cur.schedule_expr)
        tz = str(p.get("timezone") if "timezone" in p else cur.timezone)
        delivery_json = cur.delivery_json
        if "delivery" in p and isinstance(p.get("delivery"), dict):
            delivery_json = json.dumps(p["delivery"], ensure_ascii=False)
        elif "delivery_json" in p:
            delivery_json = str(p.get("delivery_json") or "{}")
        recipe_json = cur.recipe_json
        if "recipe" in p and isinstance(p.get("recipe"), dict):
            recipe_json = json.dumps(p["recipe"], ensure_ascii=False)
        elif "recipe_json" in p:
            recipe_json = str(p.get("recipe_json") or "{}")
        source_session_id = cur.source_session_id
        if "source_session_id" in p:
            raw_sid = str(p.get("source_session_id") or "").strip()
            source_session_id = raw_sid or None
        status = str(p.get("status") if "status" in p else cur.status)
        recompute = any(k in p for k in ("schedule_kind", "schedule_expr", "timezone", "status"))
        next_run_at = cur.next_run_at
        if recompute and status == "active":
            next_run_at = compute_next_run_at(
                schedule_kind=schedule_kind,
                schedule_expr=schedule_expr,
                timezone_name=tz,
                from_dt=None,
            )
        elif status != "active":
            next_run_at = None
        ts = utc_now_iso()
        with self._connect() as conn:  # type: ignore[attr-defined]
            conn.execute(
                """
                UPDATE scheduled_job SET
                    name = ?, description = ?, prompt_text = ?, recipe_json = ?, interaction_mode = ?, specialist = ?,
                    lang = ?, schedule_kind = ?, schedule_expr = ?, timezone = ?, delivery_json = ?,
                    source_session_id = ?, status = ?, next_run_at = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (
                    name,
                    description,
                    prompt_text,
                    recipe_json,
                    interaction_mode,
                    specialist,
                    lang,
                    schedule_kind,
                    schedule_expr,
                    tz,
                    delivery_json,
                    source_session_id,
                    status,
                    next_run_at,
                    ts,
                    str(job_id),
                    str(tenant_id),
                ),
            )
        return self.scheduled_job_get(job_id=job_id, tenant_id=tenant_id)

    def scheduled_job_set_status(self, *, tenant_id: str, job_id: str, status: str) -> bool:
        cur = self.scheduled_job_get(job_id=job_id, tenant_id=tenant_id)
        if not cur:
            return False
        ts = utc_now_iso()
        next_run_at = cur.next_run_at
        if status == "active":
            next_run_at = compute_next_run_at(
                schedule_kind=cur.schedule_kind,
                schedule_expr=cur.schedule_expr,
                timezone_name=cur.timezone,
                from_dt=None,
            )
        else:
            next_run_at = None
        with self._connect() as conn:  # type: ignore[attr-defined]
            cur2 = conn.execute(
                """
                UPDATE scheduled_job SET status = ?, next_run_at = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (str(status), next_run_at, ts, str(job_id), str(tenant_id)),
            )
        return bool(cur2.rowcount)

    def scheduled_job_delete(self, *, tenant_id: str, job_id: str) -> bool:
        return self.scheduled_job_set_status(tenant_id=tenant_id, job_id=job_id, status="deleted")

    def scheduled_job_list_due(self, *, limit: int = 20, now_iso: str | None = None) -> list[ScheduledJob]:
        lim = max(1, min(int(limit), 100))
        now = str(now_iso or utc_now_iso())
        with self._connect() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(
                f"""
                {_JOB_SELECT}
                WHERE status = 'active' AND next_run_at IS NOT NULL AND next_run_at <= ?
                ORDER BY next_run_at ASC
                LIMIT ?
                """,
                (now, lim),
            ).fetchall()
        return [_row_to_job(r) for r in rows]

    def scheduled_job_mark_run(
        self,
        *,
        job_id: str,
        tenant_id: str,
        last_run_status: str,
        pause_after: bool = False,
    ) -> None:
        cur = self.scheduled_job_get(job_id=job_id, tenant_id=tenant_id)
        if not cur:
            return
        ts = utc_now_iso()
        status = "paused" if pause_after else cur.status
        with self._connect() as conn:  # type: ignore[attr-defined]
            conn.execute(
                """
                UPDATE scheduled_job SET
                    last_run_at = ?, last_run_status = ?, status = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (ts, str(last_run_status), status, ts, str(job_id), str(tenant_id)),
            )

    def scheduled_job_reserve_next_run(self, *, job_id: str, tenant_id: str) -> None:
        """Advance next_run_at when a run is enqueued to avoid duplicate scheduler ticks."""
        cur = self.scheduled_job_get(job_id=job_id, tenant_id=tenant_id)
        if not cur:
            return
        ts = utc_now_iso()
        if str(cur.schedule_kind or "") == "once":
            with self._connect() as conn:  # type: ignore[attr-defined]
                conn.execute(
                    """
                    UPDATE scheduled_job SET next_run_at = NULL, status = 'paused', updated_at = ?
                    WHERE id = ? AND tenant_id = ?
                    """,
                    (ts, str(job_id), str(tenant_id)),
                )
            return
        next_run_at = compute_next_run_at(
            schedule_kind=cur.schedule_kind,
            schedule_expr=cur.schedule_expr,
            timezone_name=cur.timezone,
            from_dt=datetime.now(timezone.utc),
        )
        with self._connect() as conn:  # type: ignore[attr-defined]
            conn.execute(
                """
                UPDATE scheduled_job SET next_run_at = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (next_run_at, ts, str(job_id), str(tenant_id)),
            )

    def scheduled_job_run_create(
        self,
        *,
        job_id: str,
        tenant_id: str,
        scheduled_at: str | None = None,
        status: str = "queued",
    ) -> ScheduledJobRun:
        rid = str(uuid.uuid4())
        ts = utc_now_iso()
        sched = str(scheduled_at or ts)
        with self._connect() as conn:  # type: ignore[attr-defined]
            conn.execute(
                """
                INSERT INTO scheduled_job_run
                    (id, job_id, tenant_id, status, scheduled_at, started_at, finished_at,
                     session_id, oclaw_task_id, run_id, reply_text, delivery_status_json, error, created_at)
                VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, '', '{}', '', ?)
                """,
                (rid, str(job_id), str(tenant_id), str(status), sched, ts),
            )
        got = self.scheduled_job_run_get(run_id=rid, tenant_id=tenant_id)
        if not got:
            raise RuntimeError("failed to create scheduled job run")
        return got

    def scheduled_job_run_get(self, *, run_id: str, tenant_id: str | None = None) -> ScheduledJobRun | None:
        with self._connect() as conn:  # type: ignore[attr-defined]
            if tenant_id:
                row = conn.execute(
                    """
                    SELECT id, job_id, tenant_id, status, scheduled_at, started_at, finished_at,
                           session_id, oclaw_task_id, run_id, reply_text, delivery_status_json, error, created_at
                    FROM scheduled_job_run WHERE id = ? AND tenant_id = ?
                    """,
                    (str(run_id), str(tenant_id)),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT id, job_id, tenant_id, status, scheduled_at, started_at, finished_at,
                           session_id, oclaw_task_id, run_id, reply_text, delivery_status_json, error, created_at
                    FROM scheduled_job_run WHERE id = ?
                    """,
                    (str(run_id),),
                ).fetchone()
        if not row:
            return None
        return _row_to_run(row)

    def scheduled_job_run_list(
        self,
        *,
        job_id: str,
        tenant_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScheduledJobRun]:
        lim = max(1, min(int(limit), 200))
        off = max(0, int(offset))
        with self._connect() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(
                """
                SELECT id, job_id, tenant_id, status, scheduled_at, started_at, finished_at,
                       session_id, oclaw_task_id, run_id, reply_text, delivery_status_json, error, created_at
                FROM scheduled_job_run
                WHERE job_id = ? AND tenant_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (str(job_id), str(tenant_id), lim, off),
            ).fetchall()
        return [_row_to_run(r) for r in rows]

    def scheduled_job_run_update(
        self,
        *,
        run_id: str,
        tenant_id: str,
        patch: dict[str, Any],
    ) -> ScheduledJobRun | None:
        cur = self.scheduled_job_run_get(run_id=run_id, tenant_id=tenant_id)
        if not cur:
            return None
        p = dict(patch or {})
        status = str(p.get("status") if "status" in p else cur.status)
        started_at = p.get("started_at") if "started_at" in p else cur.started_at
        finished_at = p.get("finished_at") if "finished_at" in p else cur.finished_at
        session_id = p.get("session_id") if "session_id" in p else cur.session_id
        oclaw_task_id = p.get("oclaw_task_id") if "oclaw_task_id" in p else cur.oclaw_task_id
        agent_run_id = p.get("run_id") if "run_id" in p else cur.run_id
        reply_text = str(p.get("reply_text") if "reply_text" in p else cur.reply_text)
        delivery_status_json = cur.delivery_status_json
        if "delivery_status" in p and isinstance(p.get("delivery_status"), dict):
            delivery_status_json = json.dumps(p["delivery_status"], ensure_ascii=False)
        elif "delivery_status_json" in p:
            delivery_status_json = str(p.get("delivery_status_json") or "{}")
        error = str(p.get("error") if "error" in p else cur.error)
        with self._connect() as conn:  # type: ignore[attr-defined]
            conn.execute(
                """
                UPDATE scheduled_job_run SET
                    status = ?, started_at = ?, finished_at = ?, session_id = ?,
                    oclaw_task_id = ?, run_id = ?, reply_text = ?, delivery_status_json = ?, error = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (
                    status,
                    started_at,
                    finished_at,
                    session_id,
                    oclaw_task_id,
                    agent_run_id,
                    reply_text,
                    delivery_status_json,
                    error,
                    str(run_id),
                    str(tenant_id),
                ),
            )
        return self.scheduled_job_run_get(run_id=run_id, tenant_id=tenant_id)

    def scheduled_job_to_dict(self, job: ScheduledJob) -> dict[str, Any]:
        delivery: dict[str, Any] = {}
        try:
            raw = json.loads(job.delivery_json or "{}")
            if isinstance(raw, dict):
                delivery = raw
        except Exception:
            delivery = {}
        recipe: dict[str, Any] = {}
        try:
            raw_recipe = json.loads(job.recipe_json or "{}")
            if isinstance(raw_recipe, dict):
                recipe = raw_recipe
        except Exception:
            recipe = {}
        return {
            "id": job.id,
            "tenant_id": job.tenant_id,
            "name": job.name,
            "description": job.description,
            "status": job.status,
            "schedule_kind": job.schedule_kind,
            "schedule_expr": job.schedule_expr,
            "timezone": job.timezone,
            "prompt_text": job.prompt_text,
            "recipe": recipe,
            "interaction_mode": job.interaction_mode,
            "specialist": job.specialist,
            "lang": job.lang,
            "delivery": delivery,
            "source_session_id": job.source_session_id,
            "created_by_user_id": job.created_by_user_id,
            "source": job.source,
            "next_run_at": job.next_run_at,
            "last_run_at": job.last_run_at,
            "last_run_status": job.last_run_status,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }

    def scheduled_job_run_to_dict(self, run: ScheduledJobRun) -> dict[str, Any]:
        delivery_status: dict[str, Any] = {}
        try:
            raw = json.loads(run.delivery_status_json or "{}")
            if isinstance(raw, dict):
                delivery_status = raw
        except Exception:
            delivery_status = {}
        return {
            "id": run.id,
            "job_id": run.job_id,
            "tenant_id": run.tenant_id,
            "status": run.status,
            "scheduled_at": run.scheduled_at,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "session_id": run.session_id,
            "oclaw_task_id": run.oclaw_task_id,
            "run_id": run.run_id,
            "reply_text": run.reply_text,
            "delivery_status": delivery_status,
            "error": run.error,
            "created_at": run.created_at,
        }


__all__ = [
    "ScheduledJob",
    "ScheduledJobRun",
    "ScheduledJobStoreMixin",
    "SCHEDULED_JOB_DDL",
    "SCHEDULED_JOB_RUN_DDL",
]
