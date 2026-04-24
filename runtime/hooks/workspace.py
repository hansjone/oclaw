from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

from .frontmatter import parse_frontmatter, resolve_oclaw_metadata
from .policy import HookSource, resolve_hook_entries


HookEntry = Dict[str, Any]


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _safe_is_dir(p: Path) -> bool:
    try:
        return p.exists() and p.is_dir()
    except Exception:
        return False


def _handler_candidates() -> Tuple[str, ...]:
    return ("handler.py", "index.py")


def _load_hook_from_dir(hook_dir: Path, source: HookSource, plugin_id: Optional[str] = None) -> Optional[HookEntry]:
    hook_md = hook_dir / "HOOK.md"
    content = _read_text(hook_md)
    if content is None:
        return None

    parsed = parse_frontmatter(content)
    fm = parsed.frontmatter
    name = fm.get("name") or hook_dir.name
    if not isinstance(name, str) or not name.strip():
        name = hook_dir.name
    description = fm.get("description") or ""
    if not isinstance(description, str):
        description = ""

    handler_path: Optional[Path] = None
    for candidate in _handler_candidates():
        cand = hook_dir / candidate
        if cand.exists() and cand.is_file():
            handler_path = cand
            break
    if handler_path is None:
        return None

    metadata = resolve_oclaw_metadata(fm) or {}

    return {
        "hook": {
            "name": name,
            "description": description,
            "source": source,
            "pluginId": plugin_id,
            "filePath": str(hook_md),
            "baseDir": str(hook_dir.resolve()),
            "handlerPath": str(handler_path.resolve()),
        },
        "frontmatter": fm,
        "metadata": metadata,
    }


def load_hook_entries_from_dir(dir_path: str, source: HookSource, plugin_id: Optional[str] = None) -> List[HookEntry]:
    base = Path(dir_path)
    if not _safe_is_dir(base):
        return []
    out: List[HookEntry] = []
    try:
        for child in base.iterdir():
            if not child.is_dir():
                continue
            entry = _load_hook_from_dir(child, source=source, plugin_id=plugin_id)
            if entry:
                out.append(entry)
    except Exception:
        return out
    return out


def discover_workspace_hook_entries(
    workspace_dir: str,
    *,
    managed_hooks_dir: Optional[str] = None,
    bundled_hooks_dir: Optional[str] = None,
    extra_dirs: Optional[Sequence[str]] = None,
) -> List[HookEntry]:
    """
    Python port of Oclaw hook discovery strategy.

    - bundled: shipped with runtime
    - managed: user config dir (~/.oclaw/hooks by default)
    - workspace: <workspace>/hooks (explicit opt-in by default)
    - extra: any extra managed dirs
    """
    ws = Path(workspace_dir)
    managed = Path(managed_hooks_dir) if managed_hooks_dir else (Path.home() / ".oclaw" / "hooks")
    workspace_hooks = ws / "hooks"

    entries: List[HookEntry] = []

    if extra_dirs:
        for raw in extra_dirs:
            p = Path(os.path.expanduser(raw)).resolve()
            entries.extend(load_hook_entries_from_dir(str(p), source="oclaw-managed"))

    if bundled_hooks_dir:
        entries.extend(load_hook_entries_from_dir(bundled_hooks_dir, source="oclaw-bundled"))

    entries.extend(load_hook_entries_from_dir(str(managed), source="oclaw-managed"))
    entries.extend(load_hook_entries_from_dir(str(workspace_hooks), source="oclaw-workspace"))
    return entries


def load_workspace_hook_entries(
    workspace_dir: str,
    *,
    managed_hooks_dir: Optional[str] = None,
    bundled_hooks_dir: Optional[str] = None,
    extra_dirs: Optional[Sequence[str]] = None,
) -> List[HookEntry]:
    discovered = discover_workspace_hook_entries(
        workspace_dir,
        managed_hooks_dir=managed_hooks_dir,
        bundled_hooks_dir=bundled_hooks_dir,
        extra_dirs=extra_dirs,
    )
    return resolve_hook_entries(discovered)

