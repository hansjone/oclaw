"""OpenAI ``tools[]`` wire prep (schema complete + optional size shrink).

MCP suppression / penalty / tier / role_mode wire policy was removed.
Server visibility is controlled only by specialist↔MCP binding.
"""

from __future__ import annotations

from typing import Any

from svc.llm.tool_schema import complete_openai_tools_wire_parameters

# Legacy setting keys kept so old admin/DB rows do not break readers.
SETTINGS_KEY_PENALTY_STATE = "mcp_tool_wire_penalty_state"
SETTINGS_KEY_TOOL_POLICIES = "mcp_tool_wire_tool_policies"
SETTINGS_KEY_ADMIN_CONFIG = "mcp_tool_wire_admin_config"
SETTINGS_KEY_PENALTY_STATE_BY_ROLE = "mcp_tool_wire_penalty_state_by_role"
SETTINGS_KEY_TOOL_POLICIES_BY_ROLE = "mcp_tool_wire_tool_policies_by_role"
SETTINGS_KEY_ROLE_MODE_BY_ROLE = "mcp_tool_wire_role_mode_by_role"


def wire_policy_enabled(_base_url: str | None) -> bool:
    return False


def wire_graduation_effective(_base_url: str | None, _admin: dict[str, Any] | None = None) -> bool:
    return False


def load_merged_admin_config(_store: Any) -> dict[str, Any]:
    return {
        "wire_policy": "never",
        "top_n_full": 20,
        "stale_hours": 3.0,
        "penalty_minutes": 30.0,
        "medium_rank_start": 21,
        "medium_rank_end": 50,
        "medium_desc_chars": 520,
        "minimal_desc_cap": 80,
        "penalty_disable": True,
    }


def load_tool_policies_dict(_store: Any) -> dict[str, int]:
    return {}


def load_tool_policies_dict_for_role(_store: Any, *, role: str | None) -> dict[str, int]:
    del role
    return {}


def load_penalty_state_for_role(_store: Any, *, role: str | None) -> dict[str, Any]:
    del role
    return {}


def load_role_mode_for_role(_store: Any, *, role: str | None) -> str:
    del role
    return "unrestricted"


def filter_permanent_ban_mcp_tools(tools: list[dict[str, Any]], _policies: dict[str, int] | None = None) -> list[dict[str, Any]]:
    return list(tools or [])


def migrate_legacy_penalty_store(_store: Any) -> None:
    return None


def penalty_row_status(_row: dict[str, Any] | None, *, now: Any = None) -> str:
    del now
    return "ok"


def prepare_openai_tools_for_llm_api(
    tools: list[dict[str, Any]],
    *,
    base_url: str | None,
    max_json_bytes: int | None,
    store: Any | None = None,
    role: str | None = None,
) -> list[dict[str, Any]]:
    """Complete tool schemas and optionally shrink payload size. No MCP suppression."""
    del base_url, store, role
    if not tools:
        return tools
    out = complete_openai_tools_wire_parameters(list(tools))
    if max_json_bytes is not None and int(max_json_bytes) > 0:
        from svc.llm.tool_schema import shrink_openai_tools_payload_for_api

        out = shrink_openai_tools_payload_for_api(out, max_json_bytes=int(max_json_bytes))
        out = complete_openai_tools_wire_parameters(out)
    return out


def build_tool_wire_snapshot(store: Any, *, role: str | None = None) -> dict[str, Any]:
    """Compat stub for removed Admin wire UI."""
    del store
    return {
        "ok": True,
        "removed": True,
        "role": str(role or "").strip().lower(),
        "role_mode": "unrestricted",
        "config": load_merged_admin_config(None),
        "policies": {},
        "penalty_state": {},
        "tools": [],
        "message": "MCP wire suppression removed; use specialist MCP binding only.",
    }


__all__ = [
    "SETTINGS_KEY_PENALTY_STATE",
    "SETTINGS_KEY_TOOL_POLICIES",
    "SETTINGS_KEY_ADMIN_CONFIG",
    "SETTINGS_KEY_PENALTY_STATE_BY_ROLE",
    "SETTINGS_KEY_TOOL_POLICIES_BY_ROLE",
    "SETTINGS_KEY_ROLE_MODE_BY_ROLE",
    "build_tool_wire_snapshot",
    "filter_permanent_ban_mcp_tools",
    "load_merged_admin_config",
    "load_tool_policies_dict",
    "load_tool_policies_dict_for_role",
    "load_penalty_state_for_role",
    "load_role_mode_for_role",
    "migrate_legacy_penalty_store",
    "penalty_row_status",
    "prepare_openai_tools_for_llm_api",
    "wire_graduation_effective",
    "wire_policy_enabled",
]
