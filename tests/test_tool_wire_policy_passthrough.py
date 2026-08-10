"""Wire suppression removed: prepare_openai_tools keeps MCP tools."""

from __future__ import annotations

from svc.llm.tool_wire_policy import (
    load_role_mode_for_role,
    prepare_openai_tools_for_llm_api,
    wire_graduation_effective,
    wire_policy_enabled,
)


def test_wire_policy_disabled_by_default() -> None:
    assert wire_policy_enabled("https://api.openai.com") is False
    assert wire_graduation_effective("https://api.openai.com", {}) is False
    assert load_role_mode_for_role(None, role="ops") == "unrestricted"


def test_prepare_openai_tools_keeps_mcp_tools() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "mcp__demo__ping",
                "description": "ping",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "read",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]
    out = prepare_openai_tools_for_llm_api(
        tools,
        base_url="https://example",
        max_json_bytes=None,
        store=None,
        role="ops",
    )
    names = [
        str(((e.get("function") or {}).get("name") if isinstance(e, dict) else "") or "")
        for e in out
    ]
    assert "mcp__demo__ping" in names
    assert "read_file" in names
