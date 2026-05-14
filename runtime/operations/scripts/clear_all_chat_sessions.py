"""Delete every row in ``chat_session`` (and session-bound helper rows).

Uses the same assistant store as the gateway (SQLite or PostgreSQL per env).
Requires ``--yes`` **and** environment ``AIA_CONFIRM_CHAT_SESSION_WIPE=1`` to avoid accidental wipes.

PostgreSQL (force, avoids wiping SQLite by mistake)::

    set AIA_CONFIRM_CHAT_SESSION_WIPE=1
    python runtime/operations/scripts/clear_all_chat_sessions.py --yes --postgresql

Or use ``runtime/operations/scripts/clear_postgres_chat_sessions.ps1`` (loads ``_local/system.env`` then runs the above).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any


def _exec(store: Any, sql: str) -> None:
    with store._connect() as conn:
        conn.execute(sql)


def _try_exec(store: Any, sql: str) -> bool:
    try:
        _exec(store, sql)
        return True
    except Exception:
        return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive delete of all chat sessions.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print how many sessions exist; do not delete.",
    )
    p.add_argument(
        "--postgresql",
        action="store_true",
        help="After loading env, force AIA_ASSISTANT_DB_BACKEND=postgresql and abort unless the store is PG.",
    )
    args = p.parse_args()
    if not args.yes and not args.dry_run:
        print("Refusing to run without --yes (or use --dry-run to count only).", file=sys.stderr)
        return 2
    if args.yes and not args.dry_run and str(os.getenv("AIA_CONFIRM_CHAT_SESSION_WIPE") or "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        print(
            "Refusing destructive wipe: set environment AIA_CONFIRM_CHAT_SESSION_WIPE=1 together with --yes.",
            file=sys.stderr,
        )
        return 2

    try:
        from interfaces.http.fastapi_app import load_system_env

        load_system_env()
    except Exception:
        pass

    if args.postgresql:
        os.environ["AIA_ASSISTANT_DB_BACKEND"] = "postgresql"

    from svc.persistence.assistant_store import get_assistant_store, reset_assistant_store_singleton

    if args.postgresql:
        reset_assistant_store_singleton()

    store = get_assistant_store()
    if args.postgresql and not bool(getattr(store, "_use_pg", False)):
        print(
            "error: --postgresql was set but assistant store is not PostgreSQL "
            "(check AIA_ASSISTANT_DATABASE_URL / OPS_ASSISTANT_DATABASE_URL).",
            file=sys.stderr,
        )
        return 2
    n0 = int(store.count_sessions() or 0)
    print(f"session_count_before={n0}")
    if args.dry_run:
        return 0
    if n0 <= 0:
        print("nothing_to_do")
        return 0

    # Rows that reference sessions but are not always ON DELETE CASCADE across backends.
    for sql in (
        "DELETE FROM trace_event",
        "DELETE FROM agent_eval_log",
        "DELETE FROM oclaw_attempt",
        "DELETE FROM oclaw_run",
        "DELETE FROM oclaw_task",
        "DELETE FROM memory_vector WHERE memory_id IN (SELECT memory_id FROM memory_item WHERE session_id IN (SELECT id FROM chat_session))",
        "DELETE FROM memory_item WHERE session_id IN (SELECT id FROM chat_session)",
        "DELETE FROM memory_hit_log WHERE session_id IN (SELECT id FROM chat_session)",
    ):
        if _try_exec(store, sql):
            print(f"ok_stmt={sql[:72]}...")
        else:
            print(f"skip_stmt={sql[:72]}...")

    deleted_bulk = 0
    try:
        with store._connect() as conn:
            cur = conn.execute("DELETE FROM chat_session")
            deleted_bulk = int(getattr(cur, "rowcount", 0) or 0)
    except Exception as exc:
        print(f"bulk_delete_chat_session_failed={exc!r}; falling back to per-session delete")
        batch = 0
        while True:
            rows = store.list_sessions(limit=400, offset=0)
            if not rows:
                break
            for s in rows:
                store.delete_session(str(s.id))
                batch += 1
            if batch > 1_000_000:
                print("abort_loop_guard", file=sys.stderr)
                return 1
        deleted_bulk = batch

    n1 = int(store.count_sessions() or 0)
    print(f"deleted_sessions_bulk={deleted_bulk}")
    print(f"session_count_after={n1}")
    try:
        store._chat_messages_repo().delete_messages_where_session_missing()
        store._tool_log_queries_repo().delete_tool_logs_where_session_missing()
    except Exception as exc:
        print(f"orphan_cleanup_note={exc!r}")
    return 0 if n1 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
