#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

printf '==> Project root: %s\n' "$ROOT_DIR"
printf '==> Stopping stack services...\n'
python -m oclaw.ops stack down || true

printf '\n==> Current status\n'
python -m oclaw.ops stack status || true

