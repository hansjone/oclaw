from __future__ import annotations

from dataclasses import dataclass
import json
import os
import threading
import time
from typing import Any

from runtime.tools.mcp.env_config import mcp_row_env_config
from runtime.skills import SkillSpec, materialize_skills_from_tool_specs
from runtime.tools.base import ToolSpec
from runtime.tools.mcp.filesystem_argv import build_mcp_process_command
from runtime.tools.mcp.runtime import McpProcessRuntime
from runtime.tools.public.bailian_webparser_tool import bailian_webparser_tool


def _mcp_row_env_config(row: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    return mcp_row_env_config(row)


# Long-running netx tools exceed the generic MCP row timeout (often 30s).
# Production WA ops showed execManagedNe p90/p95 glued to ~30000ms timeouts.
_MCP_TOOL_TIMEOUT_OVERRIDES_S: dict[str, float] = {
    "execManagedNe": 320.0,
    "sqlQueryUme": 90.0,
    "findTopologyPaths": 60.0,
    "aggregateUmeAlarmsRaw": 60.0,
    "queryUmeAlarmsRaw": 60.0,
    "aggregateUmeAlarms": 60.0,
}

# Read-mostly inventory/list/alarm tools that agents re-call in tight self-loops on WhatsApp.
_MCP_LIST_CACHE_TTL_S: dict[str, float] = {
    "listCliTargets": 120.0,
    "listManagedNe": 120.0,
    "queryUmeNeInventory": 90.0,
    # Short TTL: cut identical alarm/diagnostics re-query loops in the same turn.
    "queryUmeAlarms": 45.0,
    "queryUmeAlarmsRaw": 45.0,
    "aggregateUmeAlarms": 45.0,
    "aggregateUmeAlarmsRaw": 45.0,
    "runUmeDiagnostics": 60.0,
    "findTopologyPaths": 60.0,
}

_MCP_LIST_CACHE_LOCK = threading.Lock()
_MCP_LIST_CACHE: dict[str, tuple[float, float, dict[str, Any]]] = {}


def mcp_timeout_for_tool(tool_name: str, row_timeout_s: float | None = None) -> float:
    """Resolve effective MCP tool wall-clock timeout (oclaw-side)."""
    name = str(tool_name or "").strip()
    override = _MCP_TOOL_TIMEOUT_OVERRIDES_S.get(name)
    base = float(row_timeout_s) if row_timeout_s is not None else 30.0
    if override is not None:
        return max(base, float(override))
    return max(5.0, base)


def _mcp_list_cache_ttl(tool_name: str) -> float | None:
    return _MCP_LIST_CACHE_TTL_S.get(str(tool_name or "").strip())


def _mcp_list_cache_key(server_id: str, tool_name: str, args: dict[str, Any]) -> str:
    # Keep key stable; drop obviously volatile noise keys if present.
    cleaned = {
        str(k): args.get(k)
        for k in sorted(str(x) for x in (args or {}).keys())
        if str(k) not in {"trace_id", "request_id", "run_id"}
    }
    payload = {"server_id": server_id, "tool_name": tool_name, "args": cleaned}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def _get_mcp_list_cache(key: str) -> dict[str, Any] | None:
    now = time.monotonic()
    with _MCP_LIST_CACHE_LOCK:
        hit = _MCP_LIST_CACHE.get(key)
        if not hit:
            return None
        ts, ttl, payload = hit
        if now - ts > float(ttl):
            _MCP_LIST_CACHE.pop(key, None)
            return None
        return dict(payload)


def _set_mcp_list_cache(key: str, payload: dict[str, Any], *, ttl_s: float) -> None:
    with _MCP_LIST_CACHE_LOCK:
        if len(_MCP_LIST_CACHE) >= 96:
            oldest = sorted(_MCP_LIST_CACHE.items(), key=lambda kv: kv[1][0])[:24]
            for k, _ in oldest:
                _MCP_LIST_CACHE.pop(k, None)
        _MCP_LIST_CACHE[key] = (time.monotonic(), float(ttl_s), dict(payload))


def clear_list_cli_targets_cache() -> None:
    """Clear inventory/list MCP caches (name kept for test compatibility)."""
    with _MCP_LIST_CACHE_LOCK:
        _MCP_LIST_CACHE.clear()


def clear_mcp_list_cache() -> None:
    clear_list_cli_targets_cache()


@dataclass
class _McpBoundTool:
    server_id: str
    tool_name: str
    description: str
    parameters: dict[str, Any]
    command: list[str]
    timeout_s: float = 30.0
    required_permissions: frozenset[str] = frozenset()
    env_allowlist: list[str] | None = None
    env_defaults: dict[str, str] | None = None

    def to_spec(self) -> ToolSpec:
        rt = McpProcessRuntime(
            command=self.command,
            timeout_s=self.timeout_s,
            env_allowlist=self.env_allowlist,
            env_defaults=self.env_defaults,
        )
        tool_name = self.tool_name
        server_id = self.server_id

        def _handler(args: dict[str, Any]) -> dict[str, Any]:
            call_args = dict(args or {})
            cache_ttl = _mcp_list_cache_ttl(tool_name)
            cache_key = ""
            if cache_ttl is not None:
                cache_key = _mcp_list_cache_key(server_id, tool_name, call_args)
                cached = _get_mcp_list_cache(cache_key)
                if cached is not None:
                    out = dict(cached)
                    out["cache_hit"] = True
                    out["cache_ttl_s"] = float(cache_ttl)
                    out["hint"] = (
                        out.get("hint")
                        or f"Reused {tool_name} result from short TTL cache; do not re-list before every follow-up tool."
                    )
                    return out

            res = rt.call_tool(tool_name=tool_name, arguments=call_args)
            if not isinstance(res, dict):
                return {"ok": False, "error_code": "mcp_runtime_invalid_payload", "error": "invalid_response"}
            if "ok" not in res:
                res["ok"] = False
            from runtime.tools.tool_error_hints import enrich_mcp_scope_error

            res = enrich_mcp_scope_error(res)
            if cache_ttl is not None and cache_key and res.get("ok") is not False:
                _set_mcp_list_cache(cache_key, res, ttl_s=float(cache_ttl))
                res = dict(res)
                res["cache_hit"] = False
                res["hint"] = (
                    f"Cache {tool_name} results briefly; reuse ids/rows instead of listing again in the same turn."
                )
            if tool_name == "execManagedNe" and res.get("ok") is False:
                from runtime.tools.tool_error_hints import enrich_exec_managed_ne_error

                res = enrich_exec_managed_ne_error(res)
            return res

        return ToolSpec(
            name=f"mcp__{self.server_id}__{self.tool_name}",
            description=self.description,
            parameters=self.parameters or {"type": "object", "properties": {}},
            handler=_handler,
            tags=frozenset({"mcp", "plugin"}),
            version="v1",
            risk_level="high",
            timeout_s=self.timeout_s,
            required_permissions=self.required_permissions,
            execution_mode="subprocess",
        )


def materialize_mcp_tools(store: Any, *, policy_session_id: str | None = None) -> list[ToolSpec]:
    return materialize_mcp_tools_for_specialist(
        store,
        specialist=None,
        policy_session_id=policy_session_id,
    )


def materialize_mcp_tools_for_specialist(
    store: Any,
    *,
    specialist: str | None,
    policy_session_id: str | None = None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
) -> list[ToolSpec]:
    def _is_bailian_webparser_remote_row(r: dict[str, Any]) -> bool:
        cmd2 = str(r.get("entry_command") or "").strip().lower()
        if cmd2 not in {"npx", "npx.cmd", "node"}:
            return False
        argv = [str(x or "").strip().lower() for x in (r.get("entry_args") or [])]
        joined = " ".join(argv)
        return "mcp-remote" in joined and "/api/v1/mcps/webparser/sse" in joined

    sp = str(specialist or "").strip().lower()
    if sp == "manager":
        # Manager is a first-class binding role in admin UI/config.
        # We keep it separate from generalist instead of aliasing.
        sp = "manager"
    # Preferred mapping: specialist -> server_ids
    binding_server_ids: set[str] | None = None
    try:
        if store is not None and sp:
            raw_binding = str(store.get_setting("mcp_specialist_server_binding") or "").strip()
            if raw_binding:
                obj = json.loads(raw_binding)
                if isinstance(obj, dict):
                    rows = obj.get(sp)
                    # 缺键或 null：视为未配置该专家的绑定 → 走下方「仅 coarse allowlist」逻辑（可见全部已启用 MCP）。
                    # 仅当键存在且为 JSON 数组时，才按白名单过滤（含空数组 = 刻意不给该专家任何 MCP）。
                    if rows is None:
                        binding_server_ids = None
                    elif isinstance(rows, list):
                        binding_server_ids = {str(x).strip() for x in rows if str(x).strip()}
                    else:
                        binding_server_ids = set()
    except Exception:
        binding_server_ids = None

    # Fallback to coarse specialist allowlist if no binding mapping is configured.
    raw_allowed = ""
    try:
        if store is not None:
            raw_allowed = str(store.get_setting("mcp_allowed_specialists") or "").strip()
    except Exception:
        raw_allowed = ""
    if not raw_allowed:
        raw_allowed = str(os.getenv("AIA_MCP_SPECIALISTS") or "generalist,manager").strip()
    allowed = {x.strip().lower() for x in raw_allowed.split(",") if x.strip()}
    if binding_server_ids is None and sp and sp not in allowed:
        return []
    out: list[ToolSpec] = []
    rows = store.list_mcp_servers(enabled_only=True) if store else []
    for row in rows:
        server_id = str(row.get("server_id") or "").strip()
        cmd = str(row.get("entry_command") or "").strip()
        if not server_id or not cmd:
            continue
        if binding_server_ids is not None and sp and server_id not in binding_server_ids:
            continue
        env_allowlist, env_defaults = _mcp_row_env_config(row)
        raw_args = [x for x in (row.get("entry_args") or []) if isinstance(x, str)]
        command = build_mcp_process_command(
            cmd,
            raw_args,
            store=store,
            policy_session_id=policy_session_id,
            path_policy_tenant_id=path_policy_tenant_id,
            path_policy_user_id=path_policy_user_id,
        )
        try:
            tools = store.list_mcp_server_tools(server_id=server_id)
        except Exception:
            tools = []
        for t in tools:
            tname = str(t.get("tool_name") or "")
            if _is_bailian_webparser_remote_row(row) and tname == "bailian_webparser_parse":
                compat = bailian_webparser_tool()
                out.append(
                    ToolSpec(
                        name=f"mcp__{server_id}__{tname}",
                        description=str(t.get("description") or compat.description),
                        parameters=t.get("parameters") if isinstance(t.get("parameters"), dict) else compat.parameters,
                        handler=compat.handler,
                        tags=frozenset({"mcp", "plugin", "compat"}),
                        version="v1",
                        risk_level="high",
                        timeout_s=mcp_timeout_for_tool(tname, float(row.get("timeout_s") or 30.0)),
                        required_permissions=frozenset(str(x) for x in (row.get("required_permissions") or [])),
                        execution_mode="subprocess",
                    )
                )
                continue
            spec = _McpBoundTool(
                server_id=server_id,
                tool_name=tname,
                description=str(t.get("description") or f"MCP tool {t.get('tool_name') or ''}"),
                parameters=t.get("parameters") if isinstance(t.get("parameters"), dict) else {},
                command=command,
                timeout_s=mcp_timeout_for_tool(tname, float(row.get("timeout_s") or 30.0)),
                required_permissions=frozenset(str(x) for x in (row.get("required_permissions") or [])),
                env_allowlist=env_allowlist,
                env_defaults=env_defaults,
            ).to_spec()
            out.append(spec)
    return out


def materialize_mcp_skills_for_specialist(
    store: Any,
    *,
    specialist: str | None,
    policy_session_id: str | None = None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
) -> tuple[SkillSpec, ...]:
    tools = materialize_mcp_tools_for_specialist(
        store=store,
        specialist=specialist,
        policy_session_id=policy_session_id,
        path_policy_tenant_id=path_policy_tenant_id,
        path_policy_user_id=path_policy_user_id,
    )
    return materialize_skills_from_tool_specs(tools)


__all__ = [
    "clear_list_cli_targets_cache",
    "clear_mcp_list_cache",
    "materialize_mcp_tools",
    "materialize_mcp_tools_for_specialist",
    "materialize_mcp_skills_for_specialist",
    "mcp_timeout_for_tool",
]

