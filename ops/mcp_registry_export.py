"""Build a reinstallable MCP JSON from SQLite and persist under ``oclaw/_local/`` for migration."""
from __future__ import annotations

import json
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.tools.mcp.registry import McpRegistry

_EXPORT_FILENAME = "mcp_registry_migrated.json"
_LOCAL_DIR = (PROJECT_ROOT / "oclaw" / "_local").resolve()
_EXPORT_PATH = (_LOCAL_DIR / _EXPORT_FILENAME).resolve()


def mcp_migrated_json_path() -> Path:
    return _EXPORT_PATH


def _collapse_entry_arg(arg: str, root: Path) -> str:
    """Rewrite absolute / repo-relative paths to ``__REPO_ROOT__/...`` when they exist on disk under root.

    Skips npx flags (``-y``) and tokens that are not an existing file or directory, so package names
    (e.g. ``mcp-sqlite``, ``@upstash/foo``) are not mistaken for paths.
    """
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
    servers: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        raw_args = r.get("entry_args")
        if isinstance(raw_args, list):
            entry_args = _collapse_entry_args([str(x) for x in raw_args if str(x).strip()], root)
        else:
            entry_args = []
        es = r.get("env_schema")
        env_schema = es if isinstance(es, dict) else {}
        perms = r.get("required_permissions")
        if not isinstance(perms, list):
            perms = []
        servers.append(
            {
                "server_id": str(r.get("server_id") or ""),
                "source_type": str(r.get("source_type") or ""),
                "source_ref": str(r.get("source_ref") or ""),
                "version": str(r.get("version") or ""),
                "entry_command": str(r.get("entry_command") or ""),
                "entry_args": entry_args,
                "env_schema": env_schema,
                "required_permissions": [str(x) for x in perms if str(x).strip()],
                "risk_level": str(r.get("risk_level") or "high"),
                "enabled": bool(r.get("enabled")),
                "timeout_s": float(r.get("timeout_s") or 30.0),
                "dry_run": False,
            }
        )
    return {
        "_comment": "管理台导出 / 新安装后自动落盘。可粘到「Install from JSON」；`__REPO_ROOT__/` 在管理台与 seed 中展开为仓库根。已存在路径会写成占位符，其余参数保持原样。",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "servers": servers,
    }


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
