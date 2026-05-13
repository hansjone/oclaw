from __future__ import annotations

from pathlib import Path

from svc.persistence.sqlite_store import SqliteStore
from svc.llm.tool_wire_policy import prepare_openai_tools_for_llm_api


def test_manager_role_respects_permanent_ban_by_default(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("mcp_tool_wire_tool_policies", '{"mcp__echo__ping": 9999}')
    tools = [
        {"type": "function", "function": {"name": "mcp__echo__ping", "description": "Ping", "parameters": {"type": "object"}}},
        {"type": "function", "function": {"name": "system_time", "description": "t", "parameters": {"type": "object"}}},
    ]
    out_mgr = prepare_openai_tools_for_llm_api(tools, base_url="https://example", max_json_bytes=None, store=store, role="manager")
    out_gen = prepare_openai_tools_for_llm_api(tools, base_url="https://example", max_json_bytes=None, store=store, role="generalist")
    mgr_names = {t["function"]["name"] for t in out_mgr if isinstance(t, dict) and t.get("type") == "function"}
    gen_names = {t["function"]["name"] for t in out_gen if isinstance(t, dict) and t.get("type") == "function"}
    assert "mcp__echo__ping" not in mgr_names
    assert "mcp__echo__ping" not in gen_names


def test_role_scoped_policies_override_global(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    # Global ban
    store.set_setting("mcp_tool_wire_tool_policies", '{"mcp__echo__ping": 9999}')
    # Role override allows it (policy 0)
    store.set_setting("mcp_tool_wire_tool_policies_by_role", '{"ops":{"mcp__echo__ping":0}}')
    tools = [{"type": "function", "function": {"name": "mcp__echo__ping", "description": "Ping", "parameters": {"type": "object"}}}]
    out_ops = prepare_openai_tools_for_llm_api(tools, base_url="https://example", max_json_bytes=None, store=store, role="ops")
    out_gen = prepare_openai_tools_for_llm_api(tools, base_url="https://example", max_json_bytes=None, store=store, role="generalist")
    ops_names = {t["function"]["name"] for t in out_ops if isinstance(t, dict) and t.get("type") == "function"}
    gen_names = {t["function"]["name"] for t in out_gen if isinstance(t, dict) and t.get("type") == "function"}
    assert "mcp__echo__ping" in ops_names
    assert "mcp__echo__ping" not in gen_names


def test_role_mode_unrestricted_disables_penalty_but_keeps_ban(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("mcp_tool_wire_tool_policies", '{"mcp__echo__ping": 9999}')
    store.set_setting("mcp_tool_wire_role_mode_by_role", '{"manager":"unrestricted"}')
    tools = [{"type": "function", "function": {"name": "mcp__echo__ping", "description": "Ping", "parameters": {"type": "object"}}}]
    out_mgr = prepare_openai_tools_for_llm_api(tools, base_url="https://example", max_json_bytes=None, store=store, role="manager")
    names = {t["function"]["name"] for t in out_mgr if isinstance(t, dict) and t.get("type") == "function"}
    assert "mcp__echo__ping" not in names


def test_role_mode_forbidden_disables_all_mcp(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("mcp_tool_wire_role_mode_by_role", '{"ops":"forbidden"}')
    tools = [
        {"type": "function", "function": {"name": "mcp__echo__ping", "description": "Ping", "parameters": {"type": "object"}}},
        {"type": "function", "function": {"name": "system_time", "description": "t", "parameters": {"type": "object"}}},
    ]
    out_ops = prepare_openai_tools_for_llm_api(tools, base_url="https://example", max_json_bytes=None, store=store, role="ops")
    names = {t["function"]["name"] for t in out_ops if isinstance(t, dict) and t.get("type") == "function"}
    assert "mcp__echo__ping" not in names
    assert "system_time" in names

