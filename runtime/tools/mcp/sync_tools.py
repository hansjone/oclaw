"""Sync MCP tools/list into SQLite without wire-penalty / health gating.

Health is recorded when available but must not block persisting a successful tools/list.
"""

from __future__ import annotations

from typing import Any


def is_bailian_webparser_remote(*, entry_command: str, entry_args: list[str]) -> bool:
    cmd = str(entry_command or "").strip().lower()
    if cmd not in {"npx", "npx.cmd", "node"}:
        return False
    joined = " ".join(str(x or "").strip().lower() for x in (entry_args or []))
    return "mcp-remote" in joined and "/api/v1/mcps/webparser/sse" in joined


def bailian_webparser_virtual_tools() -> list[dict[str, Any]]:
    return [
        {
            "tool_name": "bailian_webparser_parse",
            "description": "Parse webpage via DashScope WebParser compatibility mode. Requires `url` (http/https).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target webpage URL (required). Example: https://example.com"},
                    "timeout": {"type": "integer", "default": 35, "minimum": 8, "maximum": 90},
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        }
    ]


def _normalize_tools_list(items: list[Any]) -> list[dict[str, Any]]:
    norm: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        tool_name = str(it.get("tool_name") or it.get("name") or "").strip()
        if not tool_name:
            continue
        params = it.get("parameters") if isinstance(it.get("parameters"), dict) else it.get("inputSchema")
        if not isinstance(params, dict):
            params = {}
        norm.append(
            {
                "tool_name": tool_name,
                "description": str(it.get("description") or ""),
                "parameters": params,
            }
        )
    return norm


def sync_mcp_server_tools(store: Any, row: dict[str, Any]) -> dict[str, Any] | None:
    """Run tools/list (+ optional health) and persist tools.

    Unlike the old health-gated path, a failed initialize/health no longer skips sync:
    we always attempt tools/list. Health status is best-effort metadata only.
    """
    from runtime.tools.mcp.env_config import mcp_runtime_for_row

    sid = str(row.get("server_id") or "").strip()
    cmd = str(row.get("entry_command") or "").strip()
    args = [str(x) for x in (row.get("entry_args") or []) if str(x).strip()]
    if not sid:
        return None
    if not cmd:
        item: dict[str, Any] = {
            "server_id": sid,
            "ok": False,
            "error_code": "mcp_entry_missing",
            "error": "entry_command_missing",
            "health": {"ok": False, "error_code": "mcp_entry_missing", "error": "entry_command_missing"},
            "tools_synced": 0,
        }
        store.set_mcp_server_health(server_id=sid, status="error", detail=item["health"])
        return item

    if is_bailian_webparser_remote(entry_command=cmd, entry_args=args):
        tools = bailian_webparser_virtual_tools()
        store.replace_mcp_server_tools(server_id=sid, tools=tools)
        detail = {"synced_tools": len(tools), "compat_mode": "bailian_webparser"}
        store.set_mcp_server_health(server_id=sid, status="ok", detail=detail)
        return {"server_id": sid, "ok": True, "health": detail, "tools_synced": len(tools)}

    rt = mcp_runtime_for_row(row, store=store)
    health: dict[str, Any] = {}
    try:
        try:
            health = rt.health() if hasattr(rt, "health") else {}
            if not isinstance(health, dict):
                health = {}
        except Exception as exc:
            health = {"ok": False, "error_code": "mcp_healthcheck_failed", "error": f"{type(exc).__name__}: {exc}"}

        tools_res = rt.tools_list()
        if not bool(tools_res.get("ok")):
            # Persist health note but keep previous tools; do not clear catalog on transient list failure.
            detail = {
                "error_code": str(tools_res.get("error_code") or "mcp_tools_list_invalid"),
                "error": str(tools_res.get("error") or "tools_list_failed"),
                "health": health,
            }
            store.set_mcp_server_health(server_id=sid, status="error", detail=detail)
            return {
                "server_id": sid,
                "ok": False,
                "error_code": detail["error_code"],
                "error": detail["error"],
                "health": health,
                "tools_synced": 0,
            }

        tools = tools_res.get("tools") if isinstance(tools_res.get("tools"), list) else []
        norm = _normalize_tools_list(tools if isinstance(tools, list) else [])
        store.replace_mcp_server_tools(server_id=sid, tools=norm)
        health_ok = bool(health.get("ok")) if health else True
        store.set_mcp_server_health(
            server_id=sid,
            status="ok" if health_ok else "degraded",
            detail={
                "synced_tools": len(norm),
                "health_ok": health_ok,
                "health": health,
            },
        )
        return {
            "server_id": sid,
            "ok": True,
            "health": health,
            "tools_synced": len(norm),
            "health_ok": health_ok,
        }
    finally:
        try:
            rt.stop()
        except Exception:
            pass


def sync_enabled_mcp_servers(store: Any) -> dict[str, Any]:
    """Sync tools for all enabled MCP servers (used by runtime prewarm)."""
    rows = store.list_mcp_servers(enabled_only=True) if store else []
    items: list[dict[str, Any]] = []
    for row in rows or []:
        item = sync_mcp_server_tools(store, row)
        if item is not None:
            items.append(item)
    ok_count = len([x for x in items if bool(x.get("ok"))])
    return {
        "ok": True,
        "total": len(items),
        "ok_count": ok_count,
        "error_count": len(items) - ok_count,
        "items": items,
    }


__all__ = [
    "bailian_webparser_virtual_tools",
    "is_bailian_webparser_remote",
    "sync_enabled_mcp_servers",
    "sync_mcp_server_tools",
]
