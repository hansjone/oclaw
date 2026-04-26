from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path
from typing import Any, Iterable


def _resolve_state_dir() -> Path:
    override = os.environ.get("OCLAW_STATE_DIR") or os.environ.get("OCLAW_HOME")
    if override and override.strip():
        return Path(os.path.expanduser(override.strip())).resolve()
    return Path.home() / ".oclaw"


def _candidate_roots(event: Any) -> list[Path]:
    roots: list[Path] = []
    ctx = getattr(event, "context", {}) or {}
    # 1) explicit workspaceDir in hook event
    ws = ctx.get("workspaceDir") if isinstance(ctx, dict) else None
    if isinstance(ws, str) and ws.strip():
        roots.append(Path(ws).expanduser())
    # 2) OCLAW_WORKSPACE env
    env_ws = str(os.getenv("OCLAW_WORKSPACE") or "").strip()
    if env_ws:
        roots.append(Path(env_ws).expanduser())
    # 3) repo-local conventional roots
    # handler.py is under oclaw/hooks/bundled/boot-md/
    repo = Path(__file__).resolve().parents[4]
    roots.extend(
        [
            repo / "oclaw" / "runtime" / "workspaces" / "main",
            repo,
        ]
    )
    # de-dupe
    out: list[Path] = []
    seen: set[str] = set()
    for p in roots:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def handle(event: Any) -> None:
    if getattr(event, "type", None) != "gateway" or getattr(event, "action", None) != "startup":
        return

    state = _resolve_state_dir()
    log_dir = state / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    out_log = log_dir / "boot-md.log"

    now = getattr(event, "timestamp", None)
    if not isinstance(now, _dt.datetime):
        now = _dt.datetime.now(tz=_dt.timezone.utc)

    roots = _candidate_roots(event)
    checked = 0
    found = 0
    lines: list[str] = []
    for root in roots:
        checked += 1
        boot = root / "BOOT.md"
        if boot.exists() and boot.is_file():
            found += 1
            lines.append(f"[{now.isoformat()}] FOUND {boot}")
        else:
            lines.append(f"[{now.isoformat()}] MISS  {boot}")

    out_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

