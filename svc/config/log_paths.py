"""Runtime log root (gateway / channel workers / stack scripts).

Matches ``AIA_RUNTIME_LOG_DIR`` or ``<parent of assistant DB file>/logs`` — same rule as
``runtime.operations.runtime.assistant_runtime_log_dir`` but lives under ``svc.config`` to avoid
import cycles when HTTP or workers configure logging early.
"""

from __future__ import annotations

import os
from pathlib import Path

from svc.config.paths import db_path


def oclaw_log_root() -> Path:
    p = str(os.getenv("AIA_RUNTIME_LOG_DIR") or "").strip()
    if p:
        return Path(p).expanduser().resolve()
    return Path(db_path()).resolve().parent / "logs"


def oclaw_hooks_log_dir(*, state_dir_if_legacy: Path) -> Path:
    """Directory for bundled hook file logs (``command-logger``, ``boot-md``).

    Default: ``oclaw_log_root() / "hooks"`` (same tree as gateway/channel ``start_service`` logs).

    Set ``OCLAW_HOOK_LOG_USE_STATE_DIR=1`` to restore the legacy layout
    ``state_dir_if_legacy / "logs"`` (typically ``~/.oclaw/logs``).
    """
    raw = str(os.getenv("OCLAW_HOOK_LOG_USE_STATE_DIR") or "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        out = state_dir_if_legacy / "logs"
    else:
        out = oclaw_log_root() / "hooks"
    out.mkdir(parents=True, exist_ok=True)
    return out


__all__ = ["oclaw_hooks_log_dir", "oclaw_log_root"]
