"""Prune aged tool/trace noise from the assistant SQLite (or Postgres) DB.

Dry-run (default)::

    python runtime/operations/scripts/prune_sqlite_retention.py --keep-days 30

Apply delete (keeps last N days of tool messages / tool_log / traces / sent outbound)::

    python runtime/operations/scripts/prune_sqlite_retention.py --keep-days 30 --apply --yes

Also reclaim file space on SQLite (needs ~DB-size free disk; stop writers if possible)::

    python runtime/operations/scripts/prune_sqlite_retention.py --keep-days 30 --apply --yes --vacuum

Point at a specific file::

    set OPS_ASSISTANT_DB_PATH=D:\\path\\ai_ops.sqlite
    python runtime/operations/scripts/prune_sqlite_retention.py --keep-days 14 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--keep-days", type=int, default=30, help="Retain rows newer than this many days.")
    p.add_argument("--dry-run", action="store_true", default=False, help="Force dry-run (default).")
    p.add_argument("--apply", action="store_true", help="Actually delete (requires --yes).")
    p.add_argument("--yes", action="store_true", help="Confirm destructive delete.")
    p.add_argument("--vacuum", action="store_true", help="SQLite VACUUM after delete.")
    p.add_argument("--include-scheduled-runs", action="store_true", help="Also prune old scheduled_job_run.")
    p.add_argument("--no-outbound", action="store_true", help="Skip channel_outbound_message prune.")
    p.add_argument("--db", default="", help="Override OPS_ASSISTANT_DB_PATH for this run.")
    args = p.parse_args()

    if str(args.db or "").strip():
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(args.db).strip()
        os.environ["AIA_ASSISTANT_DB_BACKEND"] = "sqlite"

    from svc.persistence.assistant_store import get_assistant_store, reset_assistant_store_singleton
    from svc.persistence.sqlite_retention import prune_sqlite_retention

    reset_assistant_store_singleton()
    store = get_assistant_store()

    dry_run = not bool(args.apply)
    if args.dry_run:
        dry_run = True
    if args.apply and not args.yes:
        print("Refusing --apply without --yes", file=sys.stderr)
        return 2

    out = prune_sqlite_retention(
        store,
        keep_days=int(args.keep_days),
        dry_run=dry_run,
        vacuum=bool(args.vacuum) and not dry_run,
        include_outbound_sent=not bool(args.no_outbound),
        include_scheduled_runs=bool(args.include_scheduled_runs),
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
