from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

from .frontmatter import parse_frontmatter
from .hook_manifest_core import parse_hook_manifest
from .hook_types import HookEntry, HookInvocation, HookRef, HookSource
from .policy import resolve_hook_entries


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
    # One file per hook dir. Order: py → TypeScript (runner) → JS (node runner) → shell.
    return (
        "handler.py",
        "index.py",
        "handler.ts",
        "index.ts",
        "handler.mts",
        "index.mts",
        "handler.cts",
        "index.cts",
        "handler.mjs",
        "index.mjs",
        "handler.cjs",
        "index.cjs",
        "handler.sh",
        "index.sh",
        "handler.bash",
        "index.bash",
    )


def _resolve_contained_dir(base_dir: Path, target_dir: str) -> Optional[Path]:
    try:
        resolved = (base_dir / target_dir).resolve()
        resolved.relative_to(base_dir.resolve())
        return resolved
    except Exception:
        return None


def _parse_package_hook_paths(package_dir: Path) -> List[str]:
    """
    Support package.json manifest declarations:
    - { "openclaw": { "hooks": [...] } }
    - { "oclaw": { "hooks": [...] } }
    """
    manifest = package_dir / "package.json"
    raw = _read_text(manifest)
    if raw is None:
        return []
    try:
        obj = json.loads(raw)
    except Exception:
        return []
    if not isinstance(obj, dict):
        return []
    out: List[str] = []
    for key in ("openclaw", "oclaw"):
        row = obj.get(key)
        if not isinstance(row, dict):
            continue
        hooks = row.get("hooks")
        if not isinstance(hooks, list):
            continue
        for it in hooks:
            s = str(it or "").strip()
            if s:
                out.append(s)
        if out:
            break
    return out


def _resolve_plugin_hook_dirs(*, workspace_dir: str, config: Optional[dict[str, Any]]) -> List[tuple[str, str]]:
    """
    Lightweight Python parity for OpenClaw plugin hook discovery.

    Discover plugin bundles under:
      <workspace>/.openclaw/extensions/<plugin-id>/.codex-plugin/plugin.json
    and read `hooks` from that manifest (string path or list[str]).
    """
    ws = Path(workspace_dir).resolve()
    ext_root = ws / ".openclaw" / "extensions"
    if not ext_root.exists() or not ext_root.is_dir():
        return []

    enabled_entries = (
        (((config or {}).get("plugins") or {}).get("entries") or {})
        if isinstance((((config or {}).get("plugins") or {}).get("entries") or {}), dict)
        else {}
    )

    out: List[tuple[str, str]] = []
    seen: set[str] = set()
    for plugin_root in ext_root.iterdir():
        if not plugin_root.is_dir():
            continue
        plugin_id = plugin_root.name
        state = enabled_entries.get(plugin_id) if isinstance(enabled_entries, dict) else None
        if isinstance(state, dict) and state.get("enabled") is False:
            continue

        manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
        raw = _read_text(manifest_path)
        if raw is None:
            continue
        try:
            manifest = json.loads(raw)
        except Exception:
            continue
        if not isinstance(manifest, dict):
            continue
        hooks_value = manifest.get("hooks")
        hook_paths: List[str] = []
        if isinstance(hooks_value, str):
            s = hooks_value.strip()
            if s:
                hook_paths.append(s)
        elif isinstance(hooks_value, list):
            for row in hooks_value:
                s = str(row or "").strip()
                if s:
                    hook_paths.append(s)
        if not hook_paths:
            continue

        for rel in hook_paths:
            resolved = _resolve_contained_dir(plugin_root, rel)
            if resolved is None:
                continue
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            out.append((key, plugin_id))
    return out


def _load_hook_from_dir(hook_dir: Path, source: HookSource, plugin_id: Optional[str] = None) -> Optional[HookEntry]:
    hook_md = hook_dir / "HOOK.md"
    content = _read_text(hook_md)
    if content is None:
        return None

    parsed = parse_frontmatter(content)
    fm = parsed.frontmatter
    manifest = parse_hook_manifest(frontmatter=fm, default_name=hook_dir.name)
    name = manifest.name
    description = manifest.description

    handler_path: Optional[Path] = None
    for candidate in _handler_candidates():
        cand = hook_dir / candidate
        if cand.exists() and cand.is_file():
            handler_path = cand
            break
    if handler_path is None:
        return None

    return HookEntry(
        hook=HookRef(
            name=name,
            description=description,
            source=source,
            pluginId=plugin_id,
            filePath=str(hook_md),
            baseDir=str(hook_dir.resolve()),
            handlerPath=str(handler_path.resolve()),
        ),
        frontmatter=dict(fm),
        metadata=manifest.metadata.as_dict(),
        invocation=HookInvocation(enabled=bool(manifest.invocation_enabled)),
    )


def load_hook_entries_from_dir(dir_path: str, source: HookSource, plugin_id: Optional[str] = None) -> List[HookEntry]:
    base = Path(dir_path)
    if not _safe_is_dir(base):
        return []
    out: List[HookEntry] = []
    try:
        for child in base.iterdir():
            if not child.is_dir():
                continue
            package_hook_paths = _parse_package_hook_paths(child)
            if package_hook_paths:
                for rel in package_hook_paths:
                    hook_dir = _resolve_contained_dir(child, rel)
                    if hook_dir is None:
                        continue
                    entry = _load_hook_from_dir(hook_dir, source=source, plugin_id=plugin_id)
                    if entry:
                        out.append(entry)
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
    config: Optional[dict[str, Any]] = None,
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

    for plugin_dir, plugin_id in _resolve_plugin_hook_dirs(workspace_dir=workspace_dir, config=config):
        entries.extend(load_hook_entries_from_dir(plugin_dir, source="oclaw-plugin", plugin_id=plugin_id))

    entries.extend(load_hook_entries_from_dir(str(managed), source="oclaw-managed"))
    entries.extend(load_hook_entries_from_dir(str(workspace_hooks), source="oclaw-workspace"))
    return entries


def load_workspace_hook_entries(
    workspace_dir: str,
    *,
    config: Optional[dict[str, Any]] = None,
    managed_hooks_dir: Optional[str] = None,
    bundled_hooks_dir: Optional[str] = None,
    extra_dirs: Optional[Sequence[str]] = None,
) -> List[HookEntry]:
    discovered = discover_workspace_hook_entries(
        workspace_dir,
        config=config,
        managed_hooks_dir=managed_hooks_dir,
        bundled_hooks_dir=bundled_hooks_dir,
        extra_dirs=extra_dirs,
    )
    return resolve_hook_entries(discovered)

