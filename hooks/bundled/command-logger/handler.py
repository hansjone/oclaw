from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


def _resolve_state_dir() -> Path:
    # Keep this compatible with typical OpenClaw layouts.
    override = os.environ.get("OPENCLAW_STATE_DIR") or os.environ.get("OPENCLAW_HOME")
    if override and override.strip():
        return Path(os.path.expanduser(override.strip())).resolve()
    return Path.home() / ".openclaw"


def handle(event) -> None:
    if getattr(event, "type", None) != "command":
        return

    state_dir = _resolve_state_dir()
    log_dir = state_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    payload: Dict[str, Any] = {
        "timestamp": getattr(getattr(event, "timestamp", None), "isoformat", lambda: None)(),
        "action": getattr(event, "action", None),
        "sessionKey": getattr(event, "sessionKey", None),
        "senderId": (getattr(event, "context", {}) or {}).get("senderId", "unknown"),
        "source": (getattr(event, "context", {}) or {}).get("commandSource", "unknown"),
    }

    with (log_dir / "commands.log").open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

