#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

printf '==> Project root: %s\n' "$ROOT_DIR"
printf '==> Stack status\n'
python -m oclaw.runtime.operations stack status

printf '\n==> WeCom status\n'
python -m oclaw.runtime.operations channel wecom status

cat <<'EOF'

Admin: http://127.0.0.1:8787/admin
Chat:  http://127.0.0.1:8787/chat
EOF

