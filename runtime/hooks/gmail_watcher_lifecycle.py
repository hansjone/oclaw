from __future__ import annotations

import os
from typing import Any, Callable, Protocol

from .gmail_watcher import GmailWatcherResult, start_gmail_watcher


class GmailWatcherLog(Protocol):
    def info(self, msg: str) -> None: ...
    def warn(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


def _is_truthy_env(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _skip_gmail_watcher_env() -> bool:
    for key in ("OCLAW_SKIP_GMAIL_WATCHER", "OPENCLAW_SKIP_GMAIL_WATCHER"):
        if _is_truthy_env(os.getenv(key)):
            return True
    return False


def start_gmail_watcher_with_logs(
    *,
    cfg: dict[str, Any] | None,
    log: GmailWatcherLog,
    on_skipped: Callable[[], None] | None = None,
    starter: Callable[[dict[str, Any] | None], GmailWatcherResult] = start_gmail_watcher,
) -> None:
    """Skip entirely when ``OCLAW_SKIP_GMAIL_WATCHER`` or ``OPENCLAW_SKIP_GMAIL_WATCHER`` is truthy."""
    if _skip_gmail_watcher_env():
        if on_skipped:
            on_skipped()
        return

    try:
        res = starter(cfg)
        if bool(res.started):
            log.info("gmail watcher started")
            return
        reason = str(res.reason or "").strip()
        if reason and reason not in {
            "hooks not enabled",
            "no gmail account configured",
            "gmail watcher runtime not implemented (Python)",
        }:
            log.warn(f"gmail watcher not started: {reason}")
    except Exception as exc:
        log.error(f"gmail watcher failed to start: {exc}")

