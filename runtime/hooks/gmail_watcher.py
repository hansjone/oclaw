from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GmailWatcherResult:
    started: bool
    reason: str = ""


def start_gmail_watcher(cfg: dict[str, Any] | None) -> GmailWatcherResult:
    """
    Gmail watcher gate (OpenClaw ``startGmailWatcher`` parity, subset).

    Full ``gog`` + Gmail API + renew loop is not ported in Python yet; this
    function encodes the same **configuration preconditions** so lifecycle
    logging matches expectations.
    """
    if not isinstance(cfg, dict):
        return GmailWatcherResult(started=False, reason="no gmail account configured")

    hooks = cfg.get("hooks")
    if not isinstance(hooks, dict):
        return GmailWatcherResult(started=False, reason="hooks not enabled")

    # OpenClaw top-level ``hooks.enabled`` (when absent, treat as enabled).
    if hooks.get("enabled") is False:
        return GmailWatcherResult(started=False, reason="hooks not enabled")

    internal = hooks.get("internal") if isinstance(hooks.get("internal"), dict) else {}
    if internal.get("enabled") is False:
        return GmailWatcherResult(started=False, reason="hooks not enabled")

    gmail = hooks.get("gmail")
    if not isinstance(gmail, dict) or not str(gmail.get("account") or "").strip():
        return GmailWatcherResult(started=False, reason="no gmail account configured")

    if not shutil.which("gog"):
        return GmailWatcherResult(started=False, reason="gog binary not found")

    return GmailWatcherResult(started=False, reason="gmail watcher runtime not implemented (Python)")
