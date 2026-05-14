"""将 oclaw/data/mcp_registry.seed.json 中的 MCP 定义写入本地 SQLite（与管理台 Install 等价）。

库表被清空、换库或新环境时：在项目根执行
  python oclaw/scripts/seed_mcp_registry.py
可选：python oclaw/scripts/seed_mcp_registry.py path/to/other.seed.json

随后在各 MCP 上点 Health → Sync Tools；Context7 等需在 src/_local/mcp_local.env 配密钥。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from svc.config.paths import PROJECT_ROOT, db_path  # noqa: E402
from svc.persistence.sqlite_store import SqliteStore  # noqa: E402
from svc.persistence.assistant_store import get_assistant_store
from runtime.tools.mcp.installer import McpServerManifest, _safe_server_id, install_mcp_server  # noqa: E402


def _subst_repo(path_str: str) -> str:
    s = str(path_str or "").strip()
    if s.startswith("__REPO_ROOT__/"):
        return str((PROJECT_ROOT / s.replace("__REPO_ROOT__/", "", 1)).resolve())
    return s


def main(argv: list[str]) -> int:
    seed_path = Path(argv[1]).resolve() if len(argv) > 1 else (ROOT / "data" / "mcp_registry.seed.json")
    if not seed_path.is_file():
        print(f"seed file not found: {seed_path}", file=sys.stderr)
        return 2
    raw = json.loads(seed_path.read_text(encoding="utf-8"))
    items = raw.get("servers") if isinstance(raw, dict) else raw
    if not isinstance(items, list) or not items:
        print("no servers[] in seed file", file=sys.stderr)
        return 2

    store = get_assistant_store()
    ok_n = 0
    for payload in items:
        if not isinstance(payload, dict):
            continue
        source_type = str(payload.get("source_type") or "").strip().lower()
        source_ref = str(payload.get("source_ref") or "").strip()
        if source_type not in {"github", "npm", "pypi"} or not source_ref:
            print(f"skip invalid: {payload.get('server_id')!r}")
            continue
        server_id = _safe_server_id(str(payload.get("server_id") or source_ref))
        entry_args = [_subst_repo(x) for x in (payload.get("entry_args") or []) if str(x).strip()]
        manifest = McpServerManifest(
            server_id=server_id,
            source_type=source_type,
            source_ref=source_ref,
            version=str(payload.get("version") or "").strip(),
            entry_command=str(payload.get("entry_command") or "").strip(),
            entry_args=entry_args,
            env_schema=payload.get("env_schema") if isinstance(payload.get("env_schema"), dict) else {},
            permissions=[str(x) for x in (payload.get("required_permissions") or [])],
            risk_level=str(payload.get("risk_level") or "high"),
            enabled=bool(payload.get("enabled")),
            timeout_s=float(payload.get("timeout_s") or 30.0),
        )
        dry_run = bool(payload.get("dry_run", False))
        inst = install_mcp_server(manifest, dry_run=dry_run)
        store.upsert_mcp_server(
            server_id=manifest.server_id,
            source_type=manifest.source_type,
            source_ref=manifest.source_ref,
            version=manifest.version,
            entry_command=manifest.entry_command,
            entry_args=manifest.entry_args,
            env_schema=manifest.env_schema,
            required_permissions=manifest.permissions,
            risk_level=manifest.risk_level,
            timeout_s=manifest.timeout_s,
            enabled=manifest.enabled if inst.ok else False,
        )
        store.add_mcp_installation_log(
            server_id=manifest.server_id,
            status="ok" if inst.ok else "error",
            error_code=inst.error_code,
            detail={"error": inst.error, **(inst.details or {}), "seed": True},
            install_command=inst.install_command,
        )
        print(f"{server_id}: install_ok={inst.ok} enabled={manifest.enabled if inst.ok else False} cmd={inst.install_command[:120]!r}")
        if inst.ok:
            ok_n += 1
    print(f"done: {ok_n}/{len(items)} npm/pypi install steps succeeded; rows upserted for all valid entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
