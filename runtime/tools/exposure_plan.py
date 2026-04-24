from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from oclaw.platform.llm.tool_schema import default_max_openai_tools_json_bytes
from oclaw.platform.llm.tool_wire_policy import (
    load_merged_admin_config,
    load_role_mode_for_role,
    load_tool_policies_dict_for_role,
    prepare_openai_tools_for_llm_api,
    wire_graduation_effective,
)
from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.catalog import _is_truthy
from oclaw.runtime.tools.expert_registry import materialize_tools_for_expert, preview_expert_tools
from oclaw.runtime.tools.mcp.adapter import materialize_mcp_tools_for_specialist
from oclaw.runtime.tools.public_registry import materialize_public_tools, preview_public_tools


@dataclass(frozen=True)
class ToolExposurePlan:
    role: str
    base_url: str | None
    max_json_bytes: int | None
    mcp_enabled: bool
    role_mode: str
    wire_policy_effective: bool
    policy_keys: int
    public_risk_gate_allow_high: bool
    public_blocked_high_risk_tools: list[str]
    skipped_public: list[dict[str, Any]]
    skipped_expert: list[dict[str, Any]]
    tools_raw: list[dict[str, Any]]
    tools_wired: list[dict[str, Any]]
    removed_names: list[str]
    removed_mcp_names: list[str]
    changed_names: list[str]
    added_names: list[str]


def _tool_names(tools: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for ent in tools or []:
        if not isinstance(ent, dict) or str(ent.get("type") or "") != "function":
            continue
        fn = ent.get("function")
        if not isinstance(fn, dict):
            continue
        nm = str(fn.get("name") or "").strip()
        if nm:
            out.append(nm)
    return out


def _risk_gate_public_tools(tools: list[ToolSpec]) -> tuple[list[ToolSpec], bool, list[str]]:
    allow_high = _is_truthy(os.getenv("AIA_PUBLIC_TOOLS_ALLOW_HIGH", "0"))
    if allow_high:
        return list(tools), True, []
    kept: list[ToolSpec] = []
    blocked: list[str] = []
    for t in tools or []:
        rl = str(getattr(t, "risk_level", "") or "low").strip().lower()
        if rl == "high":
            blocked.append(str(getattr(t, "name", "") or ""))
            continue
        kept.append(t)
    return kept, False, sorted([x for x in blocked if x])


def build_internal_tool_specs(
    *,
    role: str,
    preview: bool,
) -> tuple[list[ToolSpec], dict[str, Any]]:
    """Return internal ToolSpec list (public+expert) + diagnostics.

    If preview=True, bypass caches and include skipped reasons.
    """
    r = str(role or "").strip().lower()
    pub_diag = preview_public_tools() if preview else {"tools": materialize_public_tools(), "skipped": []}
    exp_diag = preview_expert_tools(r) if preview else {"tools": materialize_tools_for_expert(r), "skipped": []}

    pub_tools = list(pub_diag.get("tools") or [])
    pub_tools, allow_high, blocked = _risk_gate_public_tools(pub_tools)
    exp_tools = list(exp_diag.get("tools") or [])
    source_by_name: dict[str, str] = {}

    merged: list[ToolSpec] = []
    seen: set[str] = set()
    for spec in list(pub_tools):
        if not isinstance(spec, ToolSpec):
            continue
        nm = str(spec.name or "").strip()
        if not nm or nm in seen:
            continue
        seen.add(nm)
        merged.append(spec)
        source_by_name[nm] = "public"
    for spec in list(exp_tools):
        if not isinstance(spec, ToolSpec):
            continue
        nm = str(spec.name or "").strip()
        if not nm or nm in seen:
            continue
        seen.add(nm)
        merged.append(spec)
        source_by_name[nm] = "expert"

    diag = {
        "public_count": len(pub_tools),
        "expert_count": len(exp_tools),
        "merged_count": len(merged),
        "public_risk_gate_allow_high": allow_high,
        "public_blocked_high_risk_tools": blocked,
        "skipped_public": list(pub_diag.get("skipped") or []),
        "skipped_expert": list(exp_diag.get("skipped") or []),
        "source_by_name": source_by_name,
    }
    return merged, diag


def build_llm_tools_plan(
    *,
    store: Any,
    role: str,
    base_url: str | None,
    max_json_bytes: int | None,
    include_mcp: bool,
    preview_internal: bool,
    raw_openai_tools_override: list[dict[str, Any]] | None = None,
) -> ToolExposurePlan:
    """Plan raw and wired OpenAI tools for a role, with consistent policy semantics."""
    r = str(role or "").strip().lower()
    bu = str(base_url or "").strip() or None
    cap = int(max_json_bytes) if isinstance(max_json_bytes, int) else None
    if cap is None:
        cap = default_max_openai_tools_json_bytes(bu)
    if cap is not None and cap <= 0:
        cap = None

    internal_specs: list[ToolSpec] = []
    diag_internal: dict[str, Any] = {
        "public_risk_gate_allow_high": bool(_is_truthy(os.getenv("AIA_PUBLIC_TOOLS_ALLOW_HIGH", "0"))),
        "public_blocked_high_risk_tools": [],
        "skipped_public": [],
        "skipped_expert": [],
    }
    if raw_openai_tools_override is None:
        internal_specs, diag_internal = build_internal_tool_specs(role=r, preview=preview_internal)

    mcp_enabled = bool(include_mcp) and (
        _is_truthy(os.getenv("AIA_ENABLE_MCP_TOOLS")) or _is_truthy(os.getenv("OPS_ENABLE_MCP_TOOLS"))
    )
    mcp_specs = materialize_mcp_tools_for_specialist(store, specialist=r) if mcp_enabled else []

    if raw_openai_tools_override is None:
        raw_specs = list(internal_specs) + list(mcp_specs)
        raw_openai_tools = [t.as_openai_tool() for t in raw_specs]
    else:
        raw_openai_tools = list(raw_openai_tools_override)

    admin_cfg = load_merged_admin_config(store)
    role_mode = load_role_mode_for_role(store, role=r)
    policies = load_tool_policies_dict_for_role(store, role=r)
    wire_effective = wire_graduation_effective(bu, admin_cfg) and role_mode == "restricted"

    wired_openai_tools = prepare_openai_tools_for_llm_api(
        raw_openai_tools,
        base_url=bu,
        max_json_bytes=cap,
        store=store,
        role=r,
    )

    raw_names = _tool_names(raw_openai_tools)
    wired_names = _tool_names(wired_openai_tools)
    raw_set = set(raw_names)
    wired_set = set(wired_names)
    removed = sorted([n for n in raw_set if n and n not in wired_set])
    added = sorted([n for n in wired_set if n and n not in raw_set])
    removed_mcp = [n for n in removed if n.startswith("mcp__")]

    # changed = same tool name but payload differs
    def _map_by_name(tools: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        m: dict[str, dict[str, Any]] = {}
        for ent in tools or []:
            if not isinstance(ent, dict) or str(ent.get("type") or "") != "function":
                continue
            fn = ent.get("function")
            if not isinstance(fn, dict):
                continue
            nm = str(fn.get("name") or "").strip()
            if nm:
                m[nm] = fn
        return m

    raw_map = _map_by_name(raw_openai_tools)
    wired_map = _map_by_name(wired_openai_tools)
    changed: list[str] = []
    for nm in sorted([n for n in wired_set if n in raw_set]):
        if raw_map.get(nm) != wired_map.get(nm):
            changed.append(nm)

    return ToolExposurePlan(
        role=r,
        base_url=bu,
        max_json_bytes=cap,
        mcp_enabled=mcp_enabled,
        role_mode=str(role_mode or "restricted"),
        wire_policy_effective=bool(wire_effective),
        policy_keys=len(policies),
        public_risk_gate_allow_high=bool(diag_internal.get("public_risk_gate_allow_high")),
        public_blocked_high_risk_tools=list(diag_internal.get("public_blocked_high_risk_tools") or []),
        skipped_public=list(diag_internal.get("skipped_public") or []),
        skipped_expert=list(diag_internal.get("skipped_expert") or []),
        tools_raw=list(raw_openai_tools),
        tools_wired=list(wired_openai_tools),
        removed_names=removed,
        removed_mcp_names=sorted(list(removed_mcp)),
        changed_names=changed,
        added_names=added,
    )


__all__ = [
    "ToolExposurePlan",
    "build_internal_tool_specs",
    "build_llm_tools_plan",
]

