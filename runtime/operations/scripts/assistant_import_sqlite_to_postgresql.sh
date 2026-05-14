#!/usr/bin/env bash
# Import assistant SQLite (db_path) into PostgreSQL. Prerequisite: alembic upgrade head on target PG.
#
# Reads _local/system.env when present (--load-system-env). Target URL: AIA_ASSISTANT_DATABASE_URL
# (or pass extra args, e.g. --pg-url 'postgresql+psycopg://...' --dry-run).
#
# Usage:
#   chmod +x runtime/operations/scripts/assistant_import_sqlite_to_postgresql.sh
#   export AIA_ASSISTANT_DATABASE_URL='postgresql+psycopg://user:pass@host:5432/oclaw'
#   ./runtime/operations/scripts/assistant_import_sqlite_to_postgresql.sh --dry-run
#   ./runtime/operations/scripts/assistant_import_sqlite_to_postgresql.sh

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
exec python "${ROOT}/runtime/operations/scripts/migrate_assistant_sqlite_to_postgresql.py" \
  --load-system-env \
  --sqlite-from-db-path \
  "$@"
