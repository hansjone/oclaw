#!/usr/bin/env bash
set -euo pipefail

CHANNEL="wecom"
SKIP_INSTALL=0
SKIP_CONFIG_HINT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-ui)
      # Kept for compatibility; stack no longer starts Streamlit.
      shift
      ;;
    --channel)
      CHANNEL="${2:-wecom}"
      shift 2
      ;;
    --skip-install)
      SKIP_INSTALL=1
      shift
      ;;
    --skip-config-hint)
      SKIP_CONFIG_HINT=1
      shift
      ;;
    *)
      echo "Unknown arg: $1"
      echo "Usage: $0 [--no-ui] [--channel wecom] [--skip-install] [--skip-config-hint]"
      echo "Note: --no-ui is legacy; stack does not start Streamlit. Chat: http://127.0.0.1:8787/chat"
      exit 1
      ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

step() { printf '\n==> %s\n' "$1"; }

if ! command -v python >/dev/null 2>&1; then
  echo "[ERROR] python not found in PATH." >&2
  exit 1
fi

step "Project root: $ROOT_DIR"
step "Python: $(command -v python)"

if [[ "$SKIP_INSTALL" -eq 0 ]]; then
  step "Installing dependencies"
  python -m pip install -r requirements.txt
else
  step "Skip dependency install"
fi

if [[ "$SKIP_CONFIG_HINT" -eq 0 ]]; then
  step "Current WeCom status"
  python -m oclaw.ops channel wecom status || true
  cat <<'EOF'

If WeCom is not configured yet, run:
  python -m oclaw.ops channel wecom config --help
EOF
fi

step "Stopping previous stack"
python -m oclaw.ops stack down || true

step "Starting stack"
python -m oclaw.ops stack up --channel "$CHANNEL"

cat <<'EOF'

Started successfully.
Admin: http://127.0.0.1:8787/admin
Chat:  http://127.0.0.1:8787/chat

Useful commands:
  python -m oclaw.ops stack status
  python -m oclaw.ops stack down
EOF

