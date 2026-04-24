from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .internal_hooks import HookHandler, register_hook, unregister_hook
from .policy import resolve_hook_enable_state, resolve_hook_config
from .workspace import HookEntry, load_workspace_hook_entries


def _load_module_from_path(module_path: str, unique_key: str) -> Optional[object]:
    """
    Dynamically import a Python module from an absolute path.
    """
    p = Path(module_path)
    if not p.exists() or not p.is_file():
        return None
    name = f"openclaw_hook_{unique_key}_{p.stem}".replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, str(p))
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[assignment]
    return mod


def _resolve_handler(mod: object, export_name: str) -> Optional[HookHandler]:
    handler = getattr(mod, export_name, None)
    if callable(handler):
        return handler  # type: ignore[return-value]
    # fallback: common names
    for candidate in ("handle", "handler", "main"):
        h = getattr(mod, candidate, None)
        if callable(h):
            return h  # type: ignore[return-value]
    return None


def load_internal_hooks(
    config: Dict[str, Any],
    workspace_dir: str,
    *,
    managed_hooks_dir: Optional[str] = None,
    bundled_hooks_dir: Optional[str] = None,
) -> int:
    """
    Discover python hooks and register them into the in-process registry.

    Hook file layout:
      <hookDir>/HOOK.md    (YAML frontmatter with openclaw metadata)
      <hookDir>/handler.py (or index.py)

    Metadata fields used:
      metadata.openclaw.events: ["type", "type:action", ...]
      metadata.openclaw.export: handler function name (default: "default" -> we map to "handle")
    """
    # Hook system is on by default; only skip when explicitly disabled.
    if (((config.get("hooks") or {}).get("internal") or {}).get("enabled")) is False:
        return 0

    entries = load_workspace_hook_entries(
        workspace_dir,
        managed_hooks_dir=managed_hooks_dir,
        bundled_hooks_dir=bundled_hooks_dir,
        extra_dirs=(((config.get("hooks") or {}).get("internal") or {}).get("load") or {}).get("extraDirs"),
    )

    loaded = 0
    for idx, entry in enumerate(entries):
        state = resolve_hook_enable_state(entry, config)
        if not state.get("enabled"):
            continue

        md = entry.get("metadata") or {}
        events = md.get("events") if isinstance(md, dict) else None
        if not isinstance(events, list) or not events:
            continue

        hook = entry.get("hook") or {}
        handler_path = hook.get("handlerPath")
        if not isinstance(handler_path, str) or not handler_path:
            continue

        export_name = md.get("export") if isinstance(md, dict) else None
        if not isinstance(export_name, str) or not export_name.strip():
            export_name = "handle"

        mod = _load_module_from_path(handler_path, unique_key=str(idx))
        if mod is None:
            continue

        handler = _resolve_handler(mod, export_name)
        if handler is None:
            continue

        for event_key in events:
            if isinstance(event_key, str) and event_key.strip():
                register_hook(event_key.strip(), handler)
        loaded += 1

    return loaded

