from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_KEEP_DAYS = 30
MAX_KEEP_DAYS = 3650
MIN_KEEP_DAYS = 1


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def cutoff_iso(*, keep_days: int, now: datetime | None = None) -> str:
    days = max(MIN_KEEP_DAYS, min(int(keep_days), MAX_KEEP_DAYS))
    base = now or _utcnow()
    return (base - timedelta(days=days)).isoformat()


def _is_postgres_store(store: Any) -> bool:
    if bool(getattr(store, "_use_pg", False)):
        return True
    url = str(getattr(store, "_postgres_url", "") or getattr(store, "db_path", "") or "")
    return url.startswith("postgres://") or url.startswith("postgresql://")


def _table_exists(conn: Any, name: str, *, postgres: bool) -> bool:
    if postgres:
        try:
            row = conn.execute("SELECT to_regclass(?)", (f"public.{name}",)).fetchone()
            if not row:
                return False
            val = row[0] if not isinstance(row, dict) else next(iter(row.values()))
            return bool(val)
        except Exception:
            return False
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)


def _length_expr(col: str, *, postgres: bool) -> str:
    if postgres:
        return f"COALESCE(LENGTH(CAST({col} AS text)), 0)"
    return f"COALESCE(LENGTH(COALESCE({col}, '')), 0)"


def _count_and_bytes(
    conn: Any,
    *,
    sql: str,
    params: tuple[Any, ...],
) -> tuple[int, int]:
    row = conn.execute(sql, params).fetchone()
    if not row:
        return 0, 0
    if isinstance(row, dict):
        vals = list(row.values())
        return int(vals[0] or 0), int(vals[1] or 0)
    return int(row[0] or 0), int(row[1] or 0)


def plan_sqlite_retention(
    store: Any,
    *,
    keep_days: int = DEFAULT_KEEP_DAYS,
    include_tool_messages: bool = True,
    include_tool_log: bool = True,
    include_trace_events: bool = True,
    include_outbound_sent: bool = True,
    include_scheduled_runs: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Dry-run friendly plan: counts + approximate payload bytes to delete."""
    cutoff = cutoff_iso(keep_days=keep_days, now=now)
    postgres = _is_postgres_store(store)
    targets: dict[str, Any] = {}
    total_rows = 0
    total_bytes = 0

    with store._connect() as conn:
        if include_tool_messages and _table_exists(conn, "chat_message", postgres=postgres):
            le = _length_expr("content", postgres=postgres)
            n, b = _count_and_bytes(
                conn,
                sql=(
                    f"SELECT COUNT(*), COALESCE(SUM({le}), 0) FROM chat_message "
                    "WHERE lower(role)='tool' AND timestamp < ?"
                ),
                params=(cutoff,),
            )
            targets["chat_message_tool"] = {"rows": n, "bytes": b, "cutoff": cutoff}
            total_rows += n
            total_bytes += b

        if include_tool_log and _table_exists(conn, "tool_log", postgres=postgres):
            le = (
                f"{_length_expr('args', postgres=postgres)} + {_length_expr('result', postgres=postgres)}"
            )
            n, b = _count_and_bytes(
                conn,
                sql=(
                    f"SELECT COUNT(*), COALESCE(SUM({le}), 0) FROM tool_log "
                    "WHERE timestamp < ?"
                ),
                params=(cutoff,),
            )
            targets["tool_log"] = {"rows": n, "bytes": b, "cutoff": cutoff}
            total_rows += n
            total_bytes += b

        if include_trace_events and _table_exists(conn, "trace_event", postgres=postgres):
            le = _length_expr("payload", postgres=postgres)
            n, b = _count_and_bytes(
                conn,
                sql=(
                    f"SELECT COUNT(*), COALESCE(SUM({le}), 0) FROM trace_event "
                    "WHERE timestamp < ?"
                ),
                params=(cutoff,),
            )
            targets["trace_event"] = {"rows": n, "bytes": b, "cutoff": cutoff}
            total_rows += n
            total_bytes += b

        if include_outbound_sent and _table_exists(
            conn, "channel_outbound_message", postgres=postgres
        ):
            le = _length_expr("text", postgres=postgres)
            n, b = _count_and_bytes(
                conn,
                sql=(
                    f"SELECT COUNT(*), COALESCE(SUM({le}), 0) FROM channel_outbound_message "
                    "WHERE created_at < ? AND lower(status) IN ('sent', 'failed', 'dead')"
                ),
                params=(cutoff,),
            )
            targets["channel_outbound_message"] = {"rows": n, "bytes": b, "cutoff": cutoff}
            total_rows += n
            total_bytes += b

        if include_scheduled_runs and _table_exists(
            conn, "scheduled_job_run", postgres=postgres
        ):
            le = (
                f"{_length_expr('reply_text', postgres=postgres)} + "
                f"{_length_expr('error', postgres=postgres)}"
            )
            n, b = _count_and_bytes(
                conn,
                sql=(
                    f"SELECT COUNT(*), COALESCE(SUM({le}), 0) FROM scheduled_job_run "
                    "WHERE created_at < ? AND lower(status) NOT IN ('queued', 'running')"
                ),
                params=(cutoff,),
            )
            targets["scheduled_job_run"] = {"rows": n, "bytes": b, "cutoff": cutoff}
            total_rows += n
            total_bytes += b

        db_size_bytes = None
        if not postgres:
            try:
                db_size_bytes = int(Path(str(store.db_path)).stat().st_size)
            except Exception:
                db_size_bytes = None

    return {
        "ok": True,
        "dry_run": True,
        "keep_days": max(MIN_KEEP_DAYS, min(int(keep_days), MAX_KEEP_DAYS)),
        "cutoff": cutoff,
        "backend": "postgresql" if postgres else "sqlite",
        "db_path": str(getattr(store, "db_path", "") or ""),
        "db_size_bytes": db_size_bytes,
        "targets": targets,
        "total_rows": total_rows,
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / 1024.0 / 1024.0, 2),
    }


def apply_sqlite_retention(
    store: Any,
    *,
    keep_days: int = DEFAULT_KEEP_DAYS,
    include_tool_messages: bool = True,
    include_tool_log: bool = True,
    include_trace_events: bool = True,
    include_outbound_sent: bool = True,
    include_scheduled_runs: bool = False,
    vacuum: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Delete aged noisy rows. Optional VACUUM (SQLite only; needs free disk ≈ DB size)."""
    plan = plan_sqlite_retention(
        store,
        keep_days=keep_days,
        include_tool_messages=include_tool_messages,
        include_tool_log=include_tool_log,
        include_trace_events=include_trace_events,
        include_outbound_sent=include_outbound_sent,
        include_scheduled_runs=include_scheduled_runs,
        now=now,
    )
    cutoff = str(plan["cutoff"])
    deleted: dict[str, int] = {}
    postgres = _is_postgres_store(store)

    with store._connect() as conn:
        if include_tool_messages and _table_exists(conn, "chat_message", postgres=postgres):
            cur = conn.execute(
                "DELETE FROM chat_message WHERE lower(role)='tool' AND timestamp < ?",
                (cutoff,),
            )
            deleted["chat_message_tool"] = int(getattr(cur, "rowcount", 0) or 0)

        if include_tool_log and _table_exists(conn, "tool_log", postgres=postgres):
            cur = conn.execute("DELETE FROM tool_log WHERE timestamp < ?", (cutoff,))
            deleted["tool_log"] = int(getattr(cur, "rowcount", 0) or 0)

        if include_trace_events and _table_exists(conn, "trace_event", postgres=postgres):
            cur = conn.execute("DELETE FROM trace_event WHERE timestamp < ?", (cutoff,))
            deleted["trace_event"] = int(getattr(cur, "rowcount", 0) or 0)

        if include_outbound_sent and _table_exists(
            conn, "channel_outbound_message", postgres=postgres
        ):
            cur = conn.execute(
                "DELETE FROM channel_outbound_message "
                "WHERE created_at < ? AND lower(status) IN ('sent', 'failed', 'dead')",
                (cutoff,),
            )
            deleted["channel_outbound_message"] = int(getattr(cur, "rowcount", 0) or 0)

        if include_scheduled_runs and _table_exists(
            conn, "scheduled_job_run", postgres=postgres
        ):
            cur = conn.execute(
                "DELETE FROM scheduled_job_run "
                "WHERE created_at < ? AND lower(status) NOT IN ('queued', 'running')",
                (cutoff,),
            )
            deleted["scheduled_job_run"] = int(getattr(cur, "rowcount", 0) or 0)

    vacuum_result: dict[str, Any] | None = None
    if vacuum:
        if postgres:
            vacuum_result = {
                "ok": False,
                "skipped": True,
                "reason": "postgresql_use_manual_vacuum",
            }
        else:
            vacuum_result = _vacuum_sqlite(store)

    db_size_after = None
    if not postgres:
        try:
            db_size_after = int(Path(str(store.db_path)).stat().st_size)
        except Exception:
            db_size_after = None

    return {
        "ok": True,
        "dry_run": False,
        "keep_days": plan["keep_days"],
        "cutoff": cutoff,
        "backend": plan["backend"],
        "db_path": plan["db_path"],
        "plan": {
            "total_rows": plan["total_rows"],
            "total_bytes": plan["total_bytes"],
            "total_mb": plan["total_mb"],
            "targets": plan["targets"],
        },
        "deleted": deleted,
        "deleted_rows": int(sum(deleted.values())),
        "db_size_bytes_before": plan.get("db_size_bytes"),
        "db_size_bytes_after": db_size_after,
        "vacuum": vacuum_result,
    }


def _vacuum_sqlite(store: Any) -> dict[str, Any]:
    path = str(getattr(store, "db_path", "") or "").strip()
    if not path or path.startswith("postgres"):
        return {"ok": False, "error": "not_sqlite"}
    try:
        dispose = getattr(store, "_dispose_engines", None)
        if callable(dispose):
            try:
                dispose()
            except Exception:
                pass
        conn = sqlite3.connect(path, timeout=120.0)
        try:
            conn.execute("VACUUM")
            conn.commit()
        finally:
            conn.close()
        size = int(Path(path).stat().st_size)
        return {"ok": True, "db_size_bytes": size}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def prune_sqlite_retention(
    store: Any,
    *,
    keep_days: int = DEFAULT_KEEP_DAYS,
    dry_run: bool = True,
    vacuum: bool = False,
    include_tool_messages: bool = True,
    include_tool_log: bool = True,
    include_trace_events: bool = True,
    include_outbound_sent: bool = True,
    include_scheduled_runs: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Entry point used by admin API / CLI."""
    if dry_run:
        return plan_sqlite_retention(
            store,
            keep_days=keep_days,
            include_tool_messages=include_tool_messages,
            include_tool_log=include_tool_log,
            include_trace_events=include_trace_events,
            include_outbound_sent=include_outbound_sent,
            include_scheduled_runs=include_scheduled_runs,
            now=now,
        )
    return apply_sqlite_retention(
        store,
        keep_days=keep_days,
        include_tool_messages=include_tool_messages,
        include_tool_log=include_tool_log,
        include_trace_events=include_trace_events,
        include_outbound_sent=include_outbound_sent,
        include_scheduled_runs=include_scheduled_runs,
        vacuum=vacuum,
        now=now,
    )


__all__ = [
    "DEFAULT_KEEP_DAYS",
    "apply_sqlite_retention",
    "cutoff_iso",
    "plan_sqlite_retention",
    "prune_sqlite_retention",
]
