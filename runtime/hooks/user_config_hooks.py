from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from svc.config.paths import PROJECT_ROOT


def resolve_hooks_config_storage_path() -> Path:
    """
    Path used for persistent ``hooks.internal.entries`` edits.

    Matches ``resolve_runtime_config`` file resolution: ``OCLAW_CONFIG_PATH`` (optional
    relative to ``PROJECT_ROOT``), else ``<PROJECT_ROOT>/oclaw.json``.
    """
    raw = str(os.getenv("OCLAW_CONFIG_PATH") or "").strip()
    if raw:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (Path(PROJECT_ROOT) / p).resolve()
        return p
    return (Path(PROJECT_ROOT) / "oclaw.json").resolve()


def load_storage_config_document() -> dict[str, Any]:
    p = resolve_hooks_config_storage_path()
    if not p.is_file():
        return {}
    try:
        raw = p.read_text(encoding="utf-8")
        obj = json.loads(raw)
        return dict(obj) if isinstance(obj, dict) else {}
    except Exception:
        return {}


def save_storage_config_document(doc: dict[str, Any]) -> None:
    p = resolve_hooks_config_storage_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)


def apply_hook_entry_enabled(
    doc: dict[str, Any],
    hook_key: str,
    enabled: bool,
    *,
    ensure_internal_hooks_enabled: bool = False,
) -> None:
    """Mutate *doc* in place (shallow structure for ``hooks.internal`` only)."""
    key = str(hook_key or "").strip()
    if not key:
        raise ValueError("hook_key is empty")

    hooks = doc.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        doc["hooks"] = {}
        hooks = doc["hooks"]

    internal = hooks.setdefault("internal", {})
    if not isinstance(internal, dict):
        hooks["internal"] = {}
        internal = hooks["internal"]

    if ensure_internal_hooks_enabled and enabled:
        internal["enabled"] = True

    entries = internal.setdefault("entries", {})
    if not isinstance(entries, dict):
        internal["entries"] = {}
        entries = internal["entries"]

    row = entries.get(key)
    if not isinstance(row, dict):
        entries[key] = {}
        row = entries[key]
    row["enabled"] = bool(enabled)
