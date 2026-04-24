"""Install MCP: SQLite (project DB), Brave Search, Google Calendar — npm global + registry upsert.

Run from repo root: python oclaw/scripts/install_mcp_sqlite_brave_calendar.py

Brave Search needs BRAVE_API_KEY in environment (+ OPS_MCP_ENV_ALLOWLIST includes it).
Google Calendar needs GOOGLE_OAUTH_CREDENTIALS=path/to/oauth.json (+ allowlist).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from oclaw.platform.config.paths import db_path  # noqa: E402
from oclaw.platform.persistence.sqlite_store import SqliteStore  # noqa: E402
from oclaw.runtime.tools.mcp.installer import McpServerManifest, install_mcp_server  # noqa: E402
from oclaw.runtime.tools.mcp.runtime import McpProcessRuntime  # noqa: E402


def _sync_tools(store: SqliteStore, server_id: str) -> bool:
    rows = store.list_mcp_servers(enabled_only=False)
    row = next((x for x in rows if str(x.get("server_id") or "") == server_id), None)
    if not row:
        return False
    cmd = str(row.get("entry_command") or "").strip()
    args = [str(x) for x in (row.get("entry_args") or []) if str(x).strip()]
    if not cmd:
        return False
    rt = McpProcessRuntime([cmd] + args, timeout_s=float(row.get("timeout_s") or 60.0))
    try:
        h = rt.health()
        if not bool(h.get("ok")):
            store.set_mcp_server_health(server_id=server_id, status="error", detail=h)
            return False
        tr = rt.tools_list()
        items = tr.get("tools") if isinstance(tr, dict) else None
        if not isinstance(items, list) or not bool(tr.get("ok")):
            store.set_mcp_server_health(server_id=server_id, status="error", detail=tr if isinstance(tr, dict) else {"error": "tools_list_failed"})
            return False
        norm: list[dict] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            tool_name = str(it.get("tool_name") or it.get("name") or "").strip()
            if not tool_name:
                continue
            norm.append(
                {
                    "tool_name": tool_name,
                    "description": str(it.get("description") or ""),
                    "parameters": it.get("parameters") if isinstance(it.get("parameters"), dict) else {},
                }
            )
        store.replace_mcp_server_tools(server_id=server_id, tools=norm)
        store.set_mcp_server_health(server_id=server_id, status="ok", detail={"synced_tools": len(norm)})
        return True
    finally:
        rt.stop()


def main() -> None:
    store = SqliteStore(db_path())
    db_file = db_path()

    bundles: list[McpServerManifest] = [
        McpServerManifest(
            server_id="mcp-sqlite",
            source_type="npm",
            source_ref="mcp-sqlite",
            version="",
            entry_command="npx",
            entry_args=["-y", "mcp-sqlite", db_file],
            env_schema={},
            permissions=[],
            risk_level="high",
            enabled=True,
            timeout_s=90.0,
        ),
        McpServerManifest(
            server_id="mcp-brave-search",
            source_type="npm",
            source_ref="@modelcontextprotocol/server-brave-search",
            version="",
            entry_command="npx",
            entry_args=["-y", "@modelcontextprotocol/server-brave-search"],
            env_schema={
                "BRAVE_API_KEY": {
                    "type": "string",
                    "description": "Brave Search API key (https://brave.com/search/api/)",
                }
            },
            permissions=[],
            risk_level="high",
            enabled=True,
            timeout_s=60.0,
        ),
        McpServerManifest(
            server_id="mcp-google-calendar",
            source_type="npm",
            source_ref="@cocal/google-calendar-mcp",
            version="",
            entry_command="npx",
            entry_args=["-y", "@cocal/google-calendar-mcp"],
            env_schema={
                "GOOGLE_OAUTH_CREDENTIALS": {
                    "type": "string",
                    "description": "Absolute path to Google Cloud OAuth client JSON (Desktop app)",
                }
            },
            permissions=[],
            risk_level="high",
            enabled=True,
            timeout_s=120.0,
        ),
    ]

    for manifest in bundles:
        print(f"\n=== npm install {manifest.server_id} ({manifest.source_ref}) ===")
        inst = install_mcp_server(manifest, dry_run=False)
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
            detail={"error": inst.error, **(inst.details or {})},
            install_command=inst.install_command,
        )
        print("install ok:", inst.ok, inst.install_command)
        if not inst.ok:
            continue
        print(f"=== sync tools {manifest.server_id} ===")
        ok = _sync_tools(store, manifest.server_id)
        print("sync ok:", ok)

    print("\nDone. If Brave/Calendar show sync errors, set env vars and OPS_MCP_ENV_ALLOWLIST, then run Check Installed from Admin.")


if __name__ == "__main__":
    main()
