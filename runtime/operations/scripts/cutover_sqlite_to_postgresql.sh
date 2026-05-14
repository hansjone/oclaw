#!/usr/bin/env bash
# Backup SQLite assistant DB, optional dry-run, then import into PostgreSQL (empty schema recommended).
#
# Loads _local/system.env via the Python migrator (--load-system-env) so AIA_ASSISTANT_DATABASE_URL /
# AIA_ASSISTANT_DB_PATH match the gateway. Override URL with extra args, e.g. --pg-url 'postgresql+...'
#
# Environment:
#   SQLITE_PATH     optional; default: db_path() after load_system_env
#   BACKUP_DIR      optional; default: <repo>/data/pg_cutover_backups
#   NO_BACKUP=1     skip file copy
#   SKIP_DRY_RUN=1  skip dry-run pass
#   DRY_RUN_ONLY=1  only dry-run
#
# Example:
#   chmod +x runtime/operations/scripts/cutover_sqlite_to_postgresql.sh
#   ./runtime/operations/scripts/cutover_sqlite_to_postgresql.sh
#   ./runtime/operations/scripts/cutover_sqlite_to_postgresql.sh --pg-url 'postgresql+psycopg://u:p@h:5432/oclaw'

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
MIG="${ROOT}/runtime/operations/scripts/migrate_assistant_sqlite_to_postgresql.py"

resolve_sqlite() {
  if [[ -n "${SQLITE_PATH:-}" ]]; then
    printf '%s' "$SQLITE_PATH"
    return
  fi
  python -c "import os,sys; sys.path.insert(0, r'''${ROOT}'''); os.chdir(r'''${ROOT}'''); from svc.config.bootstrap_env import load_system_env; load_system_env(force=True); from svc.config.paths import db_path; print(db_path(), end='')"
}

SQLITE="$(resolve_sqlite)"
if [[ ! -f "$SQLITE" ]]; then
  echo "SQLite file not found: $SQLITE" >&2
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-${ROOT}/data/pg_cutover_backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
BASE="$(basename "$SQLITE" .sqlite)"
BAK="${BACKUP_DIR}/${BASE}_pre_pg_${STAMP}.sqlite"

if [[ "${NO_BACKUP:-}" != "1" ]]; then
  cp -f "$SQLITE" "$BAK"
  echo "Backup written: $BAK"
else
  echo "NO_BACKUP=1: skipping SQLite file backup." >&2
fi

COMMON=(--load-system-env --sqlite "$SQLITE")

if [[ "${SKIP_DRY_RUN:-}" != "1" ]]; then
  echo "=== Dry-run (row counts, no PG writes) ===" >&2
  python "$MIG" "${COMMON[@]}" "$@" --dry-run
fi

if [[ "${DRY_RUN_ONLY:-}" == "1" ]]; then
  echo "DRY_RUN_ONLY=1: skipping live import." >&2
  exit 0
fi

echo "=== Live import into PostgreSQL ===" >&2
python "$MIG" "${COMMON[@]}" "$@"
echo "" >&2
echo "Done. Set AIA_ASSISTANT_DB_BACKEND=postgresql and AIA_ASSISTANT_DATABASE_URL, then restart the gateway." >&2
