from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Optional

from .config import should_include_hook_compat
from .hook_types import HookEligibilityContext, HookEntry, ensure_hook_entry
from .internal_hooks import HookHandler, register_hook, unregister_hook
from .script_handlers import build_script_hook_handler
from .workspace import load_workspace_hook_entries


_loaded_hook_registrations: list[tuple[str, HookHandler]] = []


def _reset_loaded_internal_hooks() -> None:
    while _loaded_hook_registrations:
        event_key, handler = _loaded_hook_registrations.pop()
        unregister_hook(event_key, handler)


def _is_within_base(handler_path: str, base_dir: str) -> bool:
    try:
        Path(handler_path).resolve().relative_to(Path(base_dir).resolve())
        return True
    except Exception:
        return False


def _load_module_from_path(module_path: str, unique_key: str) -> Optional[object]:
    """
    Dynamically import a Python module from an absolute path.
    """
    p = Path(module_path)
    if not p.exists() or not p.is_file():
        return None
    name = f"oclaw_hook_{unique_key}_{p.stem}".replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, str(p))
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[assignment]
    return mod


def _resolve_legacy_handlers(config: dict[str, Any]) -> list[dict[str, str]]:
    rows = (((config.get("hooks") or {}).get("internal") or {}).get("handlers"))
    if not isinstance(rows, list):
        return []
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        event = str(row.get("event") or "").strip()
        module = str(row.get("module") or "").strip()
        export = str(row.get("export") or "default").strip() or "default"
        if not event or not module:
            continue
        out.append({"event": event, "module": module, "export": export})
    return out


def _resolve_workspace_module_path(*, workspace_dir: str, raw_module: str) -> Optional[str]:
    if not raw_module or raw_module.startswith("/") or raw_module.startswith("\\"):
        return None
    ws = Path(workspace_dir).resolve()
    module_path = (ws / raw_module).resolve()
    try:
        module_path.relative_to(ws)
    except Exception:
        return None
    if not module_path.exists() or not module_path.is_file():
        return None
    return str(module_path)


def _resolve_handler(mod: object, export_name: str) -> Optional[HookHandler]:
    normalized = str(export_name or "").strip()
    if normalized and normalized != "default":
        handler = getattr(mod, normalized, None)
        if callable(handler):
            return handler  # type: ignore[return-value]
    # fallback: common names
    for candidate in ("handle", "handler", "main"):
        h = getattr(mod, candidate, None)
        if callable(h):
            return h  # type: ignore[return-value]
    return None


def load_internal_hooks(
    config: dict[str, Any],
    workspace_dir: str,
    *,
    managed_hooks_dir: Optional[str] = None,
    bundled_hooks_dir: Optional[str] = None,
    eligibility: Optional[HookEligibilityContext] = None,
) -> int:
    """
    Discover hooks and register them into the in-process registry.

    Handler files (first match wins), see ``workspace._handler_candidates`` for the full list.

    - ``.py``: in-process import (``handle`` / ``handler`` / ``main`` or ``metadata.oclaw.export``)
    - ``.ts`` / ``.mts`` / ``.cts`` (default): ``tsx`` + ``ts_hook_runner.ts`` (import ``default`` / ``handle`` or ``export``)
    - ``.mjs`` / ``.cjs`` (default): ``node`` + ``js_hook_runner.mjs`` (``import`` / ``require`` + same exports)
    - ``.sh`` / ``.bash``: subprocess: JSON on stdin, optional JSON on stdout (``context`` merge)
    - ``metadata.oclaw.hookMode: "script"`` (or legacy ``nodeScript: true``): run ``.ts`` / ``.mjs`` / ``.cjs`` as
      **stdin/stdout scripts** (no import runner) — use ``node`` for JS, ``tsx`` for TS

    Hook layout (unchanged):
      <hookDir>/HOOK.md    (YAML frontmatter with oclaw metadata)

    Metadata fields used:
      metadata.oclaw.events: ["type", "type:action", ...]
      metadata.oclaw.export: handler function name (default: "default" -> we map to "handle")
    """
    _reset_loaded_internal_hooks()

    # Hook system is on by default; only skip when explicitly disabled.
    if (((config.get("hooks") or {}).get("internal") or {}).get("enabled")) is False:
        return 0

    entries = load_workspace_hook_entries(
        workspace_dir,
        config=config,
        managed_hooks_dir=managed_hooks_dir,
        bundled_hooks_dir=bundled_hooks_dir,
        extra_dirs=(((config.get("hooks") or {}).get("internal") or {}).get("load") or {}).get("extraDirs"),
    )

    loaded = 0
    for idx, entry in enumerate(entries):
        if not should_include_hook_compat(entry=entry, config=config, eligibility=eligibility):
            continue
        entry_obj = ensure_hook_entry(entry)

        md = entry_obj.metadata or {}
        events = md.get("events") if isinstance(md, dict) else None
        if not isinstance(events, list) or not events:
            continue

        handler_path = entry_obj.hook.handlerPath
        base_dir = entry_obj.hook.baseDir
        if not isinstance(handler_path, str) or not handler_path:
            continue
        if not isinstance(base_dir, str) or not base_dir.strip():
            continue
        if not _is_within_base(handler_path, base_dir):
            continue

        export_name = md.get("export") if isinstance(md, dict) else None
        if not isinstance(export_name, str) or not export_name.strip():
            export_name = "default"

        suffix = Path(handler_path).suffix.lower()
        handler: Optional[HookHandler] = None
        if suffix in {".py"}:
            mod = _load_module_from_path(handler_path, unique_key=str(idx))
            if mod is None:
                continue
            handler = _resolve_handler(mod, export_name)
        else:
            oclaw_dict: dict[str, Any] = {}
            if isinstance(md, dict):
                for key in ("hookMode", "nodeScript"):
                    if key in md:
                        oclaw_dict[key] = md[key]
            handler = build_script_hook_handler(
                handler_path=handler_path,
                base_dir=base_dir,
                suffix=suffix,
                export_name=export_name,
                oclaw=oclaw_dict,
            )
        if handler is None:
            continue

        for event_key in events:
            if isinstance(event_key, str) and event_key.strip():
                ek = event_key.strip()
                register_hook(ek, handler)
                _loaded_hook_registrations.append((ek, handler))
        loaded += 1

    # Legacy config handlers (hooks.internal.handlers)
    for j, row in enumerate(_resolve_legacy_handlers(config)):
        safe_path = _resolve_workspace_module_path(workspace_dir=workspace_dir, raw_module=row["module"])
        if not safe_path:
            continue
        mod = _load_module_from_path(safe_path, unique_key=f"legacy_{j}")
        if mod is None:
            continue
        handler = _resolve_handler(mod, row.get("export") or "default")
        if handler is None:
            continue
        ev = row.get("event") or ""
        if not ev:
            continue
        register_hook(ev, handler)
        _loaded_hook_registrations.append((ev, handler))
        loaded += 1

    return loaded

