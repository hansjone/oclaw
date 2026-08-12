"""Build a reinstallable Cursor ``mcpServers`` JSON from SQLite under ``oclaw/_local/``."""
from __future__ import annotations

import json
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from svc.config.paths import PROJECT_ROOT
from svc.persistence.sqlite_store import SqliteStore
from runtime.tools.mcp.cursor_config import build_cursor_mcp_export
from runtime.tools.mcp.registry import McpRegistry

_EXPORT_FILENAME = "mcp_registry_migrated.json"
_LOCAL_DIR = (PROJECT_ROOT / "_local").resolve()
_EXPORT_PATH = (_LOCAL_DIR / _EXPORT_FILENAME).resolve()


def mcp_migrated_json_path() -> Path:
    return _EXPORT_PATH


def _collapse_entry_arg(arg: str, root: Path) -> str:
    """Rewrite absolute / repo-relative paths to ``__REPO_ROOT__/...`` when under root."""
    t = (arg or "").strip()
    if not t or t.startswith("__REPO_ROOT__") or t.startswith("-"):
        return str(arg)
    r = root.resolve()
    a = Path(os.path.expanduser(t))
    if not a.is_absolute():
        a = (r / t).resolve()
    else:
        a = a.resolve()
    if not a.exists():
        return str(arg)
    try:
        rel = a.relative_to(r)
    except ValueError:
        return str(arg)
    return "__REPO_ROOT__/" + rel.as_posix()


def _collapse_entry_args(args: list[str], root: Path) -> list[str]:
    return [_collapse_entry_arg(x, root) for x in args]


def build_mcp_install_export_document(store: SqliteStore) -> dict[str, Any]:
    rows = McpRegistry(store).list_servers(enabled_only=False)
    root = PROJECT_ROOT.resolve()
    collapsed: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        row = dict(r)
        raw_args = row.get("entry_args")
        if isinstance(raw_args, list):
            row["entry_args"] = _collapse_entry_args([str(x) for x in raw_args if str(x).strip()], root)
        else:
            row["entry_args"] = []
        collapsed.append(row)
    doc = build_cursor_mcp_export(collapsed)
    doc["_comment"] = (
        "Cursor mcpServers export. Paste into Admin → Plugins → Install, "
        "or feed to seed_mcp_registry.py. Paths under the repo may use __REPO_ROOT__/."
    )
    doc["exported_at"] = datetime.now(timezone.utc).isoformat()
    return doc


def persist_mcp_migrated_file(store: SqliteStore) -> str | None:
    """Write ``oclaw/_local/mcp_registry_migrated.json``. Fails open (warn only). Returns path or None."""
    try:
        mcp_migrated_json_path().parent.mkdir(parents=True, exist_ok=True)
        doc = build_mcp_install_export_document(store)
        path = mcp_migrated_json_path()
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return str(path)
    except OSError as exc:
        warnings.warn(f"mcp_registry_migrated write failed: {exc}", RuntimeWarning, stacklevel=1)
        return None


__all__ = [
    "build_mcp_install_export_document",
    "mcp_migrated_json_path",
    "persist_mcp_migrated_file",
]
