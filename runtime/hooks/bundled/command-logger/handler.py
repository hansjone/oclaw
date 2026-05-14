from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from svc.config.log_paths import oclaw_hooks_log_dir


def _resolve_state_dir() -> Path:
    # Keep this compatible with typical Oclaw layouts.
    override = os.environ.get("OCLAW_STATE_DIR") or os.environ.get("OCLAW_HOME")
    if override and override.strip():
        return Path(os.path.expanduser(override.strip())).resolve()
    return Path.home() / ".oclaw"


def handle(event) -> None:
    if getattr(event, "type", None) != "command":
        return

    log_dir = oclaw_hooks_log_dir(state_dir_if_legacy=_resolve_state_dir())

    payload: Dict[str, Any] = {
        "timestamp": getattr(getattr(event, "timestamp", None), "isoformat", lambda: None)(),
        "action": getattr(event, "action", None),
        "sessionKey": getattr(event, "sessionKey", None),
        "senderId": (getattr(event, "context", {}) or {}).get("senderId", "unknown"),
        "source": (getattr(event, "context", {}) or {}).get("commandSource", "unknown"),
    }

    with (log_dir / "commands.log").open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

