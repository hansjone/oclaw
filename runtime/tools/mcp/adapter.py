from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any

from oclaw.runtime.operations.mcp_env import mcp_env_allowlist_keys
from oclaw.runtime.skills import SkillSpec, materialize_skills_from_tool_specs
from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.mcp.filesystem_argv import build_mcp_process_command
from oclaw.runtime.tools.mcp.runtime import McpProcessRuntime


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

    def to_spec(self) -> ToolSpec:
        rt = McpProcessRuntime(command=self.command, timeout_s=self.timeout_s, env_allowlist=self.env_allowlist)

        def _handler(args: dict[str, Any]) -> dict[str, Any]:
            res = rt.call_tool(tool_name=self.tool_name, arguments=args or {})
            if not isinstance(res, dict):
                return {"ok": False, "error_code": "mcp_runtime_invalid_payload", "error": "invalid_response"}
            if "ok" not in res:
                res["ok"] = False
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
    env_allowlist = mcp_env_allowlist_keys()
    for row in rows:
        server_id = str(row.get("server_id") or "").strip()
        cmd = str(row.get("entry_command") or "").strip()
        if not server_id or not cmd:
            continue
        if binding_server_ids is not None and sp and server_id not in binding_server_ids:
            continue
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
            spec = _McpBoundTool(
                server_id=server_id,
                tool_name=str(t.get("tool_name") or ""),
                description=str(t.get("description") or f"MCP tool {t.get('tool_name') or ''}"),
                parameters=t.get("parameters") if isinstance(t.get("parameters"), dict) else {},
                command=command,
                timeout_s=float(row.get("timeout_s") or 30.0),
                required_permissions=frozenset(str(x) for x in (row.get("required_permissions") or [])),
                env_allowlist=env_allowlist,
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
    "materialize_mcp_tools",
    "materialize_mcp_tools_for_specialist",
    "materialize_mcp_skills_for_specialist",
]

