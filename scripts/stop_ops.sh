#!/usr/bin/env bash
set -euo pipefail

REAL_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../runtime/operations/scripts" && pwd)/stop_ops.sh"
if [[ ! -f "$REAL_PATH" ]]; then
  echo "[ERROR] Forward script target not found: $REAL_PATH" >&2
  exit 1
fi

exec bash "$REAL_PATH" "$@"

