from __future__ import annotations

import datetime as _dt
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


HOOK_KEY = "session-memory"


def _ensure_repo_imports() -> None:
    # Allow importing repository modules when hook is loaded by path.
    # handler.py is under oclaw/hooks/bundled/session-memory/
    repo = Path(__file__).resolve().parents[5]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))


def _resolve_hook_cfg(cfg: Any) -> Dict[str, Any]:
    if not isinstance(cfg, dict):
        return {}
    hooks = cfg.get("hooks") if isinstance(cfg.get("hooks"), dict) else {}
    internal = hooks.get("internal") if isinstance(hooks.get("internal"), dict) else {}
    entries = internal.get("entries") if isinstance(internal.get("entries"), dict) else {}
    row = entries.get(HOOK_KEY)
    return row if isinstance(row, dict) else {}


_SLUG_SAFE_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str, *, max_len: int = 40) -> str:
    s = (text or "").strip().lower()
    s = _SLUG_SAFE_RE.sub("-", s).strip("-")
    if not s:
        return ""
    s = s[:max_len].strip("-")
    return s or ""


def _fallback_time_slug(ts: _dt.datetime) -> str:
    return ts.strftime("%H%M")


def _workspace_dir_from_event(event: Any) -> Optional[Path]:
    ctx = getattr(event, "context", None)
    if not isinstance(ctx, dict):
        return None
    ws = ctx.get("workspaceDir")
    if isinstance(ws, str) and ws.strip():
        return Path(ws).expanduser()
    env_ws = str(os.getenv("OPENCLAW_WORKSPACE") or "").strip()
    if env_ws:
        return Path(env_ws).expanduser()
    return None


def _recent_conversation_lines(msgs: List[Any], *, max_pairs: int) -> str:
    """
    Render a minimal markdown "conversation" block.
    """
    # Keep only user/assistant/tool-ish messages; show role prefixes.
    lines: list[str] = []
    for m in msgs[-max(1, max_pairs * 2) :]:
        role = str(getattr(m, "role", "") or "").strip() or "unknown"
        content = str(getattr(m, "content", "") or "").strip()
        if not content:
            continue
        if role.lower() == "assistant":
            prefix = "Assistant"
        elif role.lower() == "user":
            prefix = "User"
        else:
            prefix = role
        lines.append(f"- **{prefix}**: {content}")
    return "\n".join(lines).strip()


def handle(event: Any) -> None:
    # Only trigger on command new/reset
    if getattr(event, "type", None) != "command":
        return
    action = str(getattr(event, "action", "") or "").strip().lower()
    if action not in {"new", "reset"}:
        return

    ctx = getattr(event, "context", None)
    if not isinstance(ctx, dict):
        ctx = {}

    cfg = ctx.get("cfg")
    hook_cfg = _resolve_hook_cfg(cfg)
    if hook_cfg.get("enabled") is False:
        return

    max_msgs = hook_cfg.get("messages")
    try:
        max_msgs_n = int(max_msgs) if max_msgs is not None else 15
    except Exception:
        max_msgs_n = 15
    max_msgs_n = max(5, min(max_msgs_n, 200))

    ts = getattr(event, "timestamp", None)
    if not isinstance(ts, _dt.datetime):
        ts = _dt.datetime.now(tz=_dt.timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=_dt.timezone.utc)

    ws_dir = _workspace_dir_from_event(event)
    if ws_dir is None:
        # Nothing to do without a workspace dir target.
        return
    ws_dir.mkdir(parents=True, exist_ok=True)
    mem_dir = ws_dir / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)

    session_id = str(getattr(event, "sessionKey", "") or "").strip() or "unknown"

    # Fetch recent messages from sqlite.
    try:
        _ensure_repo_imports()
        from oclaw.platform.config.paths import db_path  # type: ignore
        from oclaw.platform.persistence.sqlite_store import SqliteStore  # type: ignore

        store = SqliteStore(db_path())
        msgs = store.get_messages(session_id=session_id, limit=max_msgs_n)
    except Exception:
        msgs = []

    convo = _recent_conversation_lines(list(msgs or []), max_pairs=max_msgs_n)

    # Build slug from first user message in window.
    base_slug = ""
    for m in list(msgs or []):
        if str(getattr(m, "role", "") or "").strip().lower() != "user":
            continue
        t = str(getattr(m, "content", "") or "").strip()
        if t:
            base_slug = _slugify(t)
            break
    if not base_slug:
        base_slug = _fallback_time_slug(ts)

    date_str = ts.date().isoformat()
    filename = f"{date_str}-{base_slug}.md"
    target = mem_dir / filename

    header = [
        f"# Session: {date_str} {ts.strftime('%H:%M:%S')} UTC",
        "",
        f"- **Session Key**: {session_id}",
        f"- **Action**: {action}",
        "",
    ]
    body: list[str] = []
    if convo:
        body.extend(["## Conversation Summary", "", convo, ""])
    else:
        body.extend(["## Conversation Summary", "", "- (no messages found)", ""])

    target.write_text("\n".join(header + body).strip() + "\n", encoding="utf-8")

