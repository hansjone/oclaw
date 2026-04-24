from __future__ import annotations

from pathlib import Path

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.tools.catalog import materialize_tool_specs


def _seed_single_mcp_tool(store: SqliteStore) -> None:
    store.upsert_mcp_server(
        server_id="echo",
        source_type="github",
        source_ref="https://github.com/acme/echo",
        entry_command="python",
        entry_args=["-m", "echo_server"],
        enabled=True,
    )
    store.replace_mcp_server_tools(
        server_id="echo",
        tools=[{"tool_name": "ping", "description": "Ping", "parameters": {"type": "object", "properties": {}}}],
    )


def test_catalog_materializes_mcp_tools_when_enabled(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    _seed_single_mcp_tool(store)
    store.set_setting("AIA_ENABLE_MCP_TOOLS", "1")
    specs = materialize_tool_specs(store=store, specialist="generalist")
    names = {x.name for x in specs}
    assert "system_time" in names
    assert "mcp__echo__ping" in names


def test_catalog_skips_mcp_tools_when_disabled(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    _seed_single_mcp_tool(store)
    store.set_setting("AIA_ENABLE_MCP_TOOLS", "0")
    specs = materialize_tool_specs(store=store, specialist="generalist")
    names = {x.name for x in specs}
    assert "system_time" in names
    assert "mcp__echo__ping" not in names

