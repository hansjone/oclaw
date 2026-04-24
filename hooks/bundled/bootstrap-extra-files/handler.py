from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


HOOK_KEY = "bootstrap-extra-files"
_ALLOWED_BASENAMES = {
    "AGENTS.md",
    "SOUL.md",
    "TOOLS.md",
    "IDENTITY.md",
    "USER.md",
    "HEARTBEAT.md",
    "BOOTSTRAP.md",
    "MEMORY.md",
    "memory.md",
}


def _resolve_hook_cfg(cfg: Any) -> Dict[str, Any]:
    if not isinstance(cfg, dict):
        return {}
    hooks = cfg.get("hooks") if isinstance(cfg.get("hooks"), dict) else {}
    internal = hooks.get("internal") if isinstance(hooks.get("internal"), dict) else {}
    entries = internal.get("entries") if isinstance(internal.get("entries"), dict) else {}
    row = entries.get(HOOK_KEY)
    return row if isinstance(row, dict) else {}


def _string_list(v: Any) -> List[str]:
    if isinstance(v, list):
        out = []
        for x in v:
            s = str(x or "").strip()
            if s:
                out.append(s)
        return out
    if isinstance(v, str):
        s = v.strip()
        return [s] if s else []
    return []


def _patterns(hook_cfg: Dict[str, Any]) -> List[str]:
    for k in ("paths", "patterns", "files"):
        got = _string_list(hook_cfg.get(k))
        if got:
            return got
    return []


def _is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _glob_paths(root: Path, patterns: Sequence[str]) -> List[Path]:
    """
    We intentionally do not use Path.glob on arbitrary patterns that might escape roots via '..'.
    Instead: enumerate candidates by rglob and fnmatch on posix-style relative paths.
    """
    if not root.exists() or not root.is_dir():
        return []

    # Pre-normalize patterns to forward-slash for fnmatch
    raw_pats = [p.replace("\\", "/").lstrip("/") for p in patterns if str(p or "").strip()]
    pats: list[str] = []
    for pat in raw_pats:
        pats.append(pat)
        # Python's fnmatch doesn't treat "**/" as "zero-or-more directories".
        # Add a compatibility variant so "**/AGENTS.md" matches "AGENTS.md" as well.
        if pat.startswith("**/") and len(pat) > 3:
            pats.append(pat[3:])
    if not pats:
        return []

    out: List[Path] = []
    try:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.name not in _ALLOWED_BASENAMES:
                continue
            rel = p.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(rel, pat) for pat in pats):
                out.append(p)
    except Exception:
        return out

    # deterministic order
    out.sort(key=lambda x: x.as_posix())
    return out


def handle(event: Any) -> None:
    if getattr(event, "type", None) != "agent" or getattr(event, "action", None) != "bootstrap":
        return

    ctx = getattr(event, "context", None)
    if not isinstance(ctx, dict):
        return

    hook_cfg = _resolve_hook_cfg(ctx.get("cfg"))
    if hook_cfg.get("enabled") is False:
        return

    patterns = _patterns(hook_cfg)
    if not patterns:
        return

    ws = ctx.get("workspaceDir")
    if not isinstance(ws, str) or not ws.strip():
        return
    ws_root = Path(ws).expanduser()
    if not ws_root.exists() or not ws_root.is_dir():
        return

    matches = _glob_paths(ws_root, patterns)
    if not matches:
        return

    # Mutate context.bootstrapFiles (OpenClaw-style).
    boot = ctx.get("bootstrapFiles")
    if not isinstance(boot, list):
        boot = []
        ctx["bootstrapFiles"] = boot

    existing_paths = set()
    for it in list(boot):
        if isinstance(it, dict) and isinstance(it.get("path"), str):
            existing_paths.add(it["path"])
        elif isinstance(it, str):
            existing_paths.add(it)

    for p in matches:
        ap = str(p.resolve())
        if ap in existing_paths:
            continue
        boot.append({"path": ap, "name": p.name})
        existing_paths.add(ap)

