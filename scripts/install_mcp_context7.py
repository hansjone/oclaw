"""Install MCP: Context7 (up-to-date library docs) — npm global + registry + Sync Tools + generalist binding.

Run from repo root: python oclaw/scripts/install_mcp_context7.py

Requires CONTEXT7_API_KEY in src/_local/mcp_local.env or data/mcp_local.env (or environment). Default OPS_MCP_ENV_ALLOWLIST
now includes CONTEXT7_API_KEY when unset; restart gateway after changing env.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from oclaw.platform.config.paths import db_path  # noqa: E402
from oclaw.platform.persistence.sqlite_store import SqliteStore  # noqa: E402
from oclaw.tools.mcp.installer import McpServerManifest, install_mcp_server  # noqa: E402
from oclaw.tools.mcp.runtime import McpProcessRuntime  # noqa: E402

_BINDING_KEY = "mcp_specialist_server_binding"


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
            store.set_mcp_server_health(
                server_id=server_id,
                status="error",
                detail=tr if isinstance(tr, dict) else {"error": "tools_list_failed"},
            )
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


def _append_generalist_binding(store: SqliteStore, server_id: str) -> None:
    raw = str(store.get_setting(_BINDING_KEY) or "").strip()
    try:
        obj = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        obj = {}
    if not isinstance(obj, dict):
        obj = {}
    cur = obj.get("generalist")
    gl: list[str] = list(cur) if isinstance(cur, list) else []
    sid = str(server_id or "").strip()
    if sid and sid not in gl:
        gl.append(sid)
    obj["generalist"] = gl
    store.set_setting(_BINDING_KEY, json.dumps(obj, ensure_ascii=False))


def main() -> None:
    store = SqliteStore(db_path())
    manifest = McpServerManifest(
        server_id="mcp-context7",
        source_type="npm",
        source_ref="@upstash/context7-mcp",
        version="",
        entry_command="npx",
        entry_args=["-y", "@upstash/context7-mcp"],
        env_schema={
            "CONTEXT7_API_KEY": {
                "type": "string",
                "description": "Context7 API key (https://context7.com/dashboard)",
            }
        },
        permissions=[],
        risk_level="medium",
        enabled=True,
        timeout_s=60.0,
    )
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
        return
    print(f"=== sync tools {manifest.server_id} ===")
    synced = _sync_tools(store, manifest.server_id)
    print("sync ok:", synced)
    if synced:
        _append_generalist_binding(store, manifest.server_id)
        print("binding: appended mcp-context7 to generalist")
    else:
        print("Set CONTEXT7_API_KEY in src/_local/mcp_local.env (or data/mcp_local.env), restart gateway, then Admin → Sync Tools; save binding with mcp-context7 if needed.")

    print("\nDone.")


if __name__ == "__main__":
    main()
