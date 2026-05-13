from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from svc.persistence.sqlite_store import SqliteStore
from runtime.tools.mcp.adapter import materialize_mcp_tools, materialize_mcp_tools_for_specialist


class McpAdapterTests(unittest.TestCase):
    def test_materialize_mcp_tools(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            store = SqliteStore(str(Path(td) / "ops.sqlite"))
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
            specs = materialize_mcp_tools(store)
            self.assertEqual(len(specs), 1)
            self.assertEqual(specs[0].name, "mcp__echo__ping")

    def test_specialist_filter(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            store = SqliteStore(str(Path(td) / "ops.sqlite"))
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
            store.set_setting("mcp_allowed_specialists", "generalist")
            g_specs = materialize_mcp_tools_for_specialist(store, specialist="generalist")
            o_specs = materialize_mcp_tools_for_specialist(store, specialist="ops")
            self.assertEqual(len(g_specs), 1)
            self.assertEqual(len(o_specs), 0)

    def test_specialist_binding_filter(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            store = SqliteStore(str(Path(td) / "ops.sqlite"))
            store.upsert_mcp_server(
                server_id="echo-a",
                source_type="github",
                source_ref="https://github.com/acme/a",
                entry_command="python",
                entry_args=["-m", "a_server"],
                enabled=True,
            )
            store.upsert_mcp_server(
                server_id="echo-b",
                source_type="github",
                source_ref="https://github.com/acme/b",
                entry_command="python",
                entry_args=["-m", "b_server"],
                enabled=True,
            )
            store.replace_mcp_server_tools(
                server_id="echo-a",
                tools=[{"tool_name": "ping_a", "description": "Ping A", "parameters": {"type": "object", "properties": {}}}],
            )
            store.replace_mcp_server_tools(
                server_id="echo-b",
                tools=[{"tool_name": "ping_b", "description": "Ping B", "parameters": {"type": "object", "properties": {}}}],
            )
            store.set_setting("mcp_specialist_server_binding", '{"generalist":["echo-a"],"ops":["echo-b"]}')
            g_specs = materialize_mcp_tools_for_specialist(store, specialist="generalist")
            o_specs = materialize_mcp_tools_for_specialist(store, specialist="ops")
            g_names = {x.name for x in g_specs}
            o_names = {x.name for x in o_specs}
            self.assertIn("mcp__echo-a__ping_a", g_names)
            self.assertNotIn("mcp__echo-b__ping_b", g_names)
            self.assertIn("mcp__echo-b__ping_b", o_names)
            self.assertNotIn("mcp__echo-a__ping_a", o_names)

    def test_manager_binding_filter(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            store = SqliteStore(str(Path(td) / "ops.sqlite"))
            store.upsert_mcp_server(
                server_id="echo-a",
                source_type="github",
                source_ref="https://github.com/acme/a",
                entry_command="python",
                entry_args=["-m", "a_server"],
                enabled=True,
            )
            store.upsert_mcp_server(
                server_id="echo-b",
                source_type="github",
                source_ref="https://github.com/acme/b",
                entry_command="python",
                entry_args=["-m", "b_server"],
                enabled=True,
            )
            store.replace_mcp_server_tools(
                server_id="echo-a",
                tools=[{"tool_name": "ping_a", "description": "Ping A", "parameters": {"type": "object", "properties": {}}}],
            )
            store.replace_mcp_server_tools(
                server_id="echo-b",
                tools=[{"tool_name": "ping_b", "description": "Ping B", "parameters": {"type": "object", "properties": {}}}],
            )
            store.set_setting("mcp_specialist_server_binding", '{"manager":["echo-a"],"generalist":["echo-b"]}')
            m_specs = materialize_mcp_tools_for_specialist(store, specialist="manager")
            g_specs = materialize_mcp_tools_for_specialist(store, specialist="generalist")
            m_names = {x.name for x in m_specs}
            g_names = {x.name for x in g_specs}
            self.assertIn("mcp__echo-a__ping_a", m_names)
            self.assertNotIn("mcp__echo-b__ping_b", m_names)
            self.assertIn("mcp__echo-b__ping_b", g_names)

    def test_binding_empty_json_object_falls_back_to_all_mcp_for_specialist(self) -> None:
        """{} 不应把每个专家都当成「已绑定但列表为空」而屏蔽全部 MCP。"""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            store = SqliteStore(str(Path(td) / "ops.sqlite"))
            for sid in ("echo-a", "echo-b"):
                store.upsert_mcp_server(
                    server_id=sid,
                    source_type="github",
                    source_ref=f"https://github.com/acme/{sid}",
                    entry_command="python",
                    entry_args=["-m", "x"],
                    enabled=True,
                )
                store.replace_mcp_server_tools(
                    server_id=sid,
                    tools=[{"tool_name": "ping", "description": "P", "parameters": {"type": "object", "properties": {}}}],
                )
            store.set_setting("mcp_specialist_server_binding", "{}")
            g_specs = materialize_mcp_tools_for_specialist(store, specialist="generalist")
            names = {x.name for x in g_specs}
            self.assertIn("mcp__echo-a__ping", names)
            self.assertIn("mcp__echo-b__ping", names)

    def test_mcp_local_env_file_path_prefers_src_local(self) -> None:
        from runtime.operations import mcp_env

        p = mcp_env.mcp_local_env_file_path()
        self.assertEqual(p.name, "mcp_local.env")
        parts = {x.replace("\\", "/") for x in p.parts}
        self.assertIn("oclaw", parts)
        self.assertIn("_local", parts)

    def test_mcp_env_allowlist_keys_default_when_unset(self) -> None:
        from runtime.operations import mcp_env

        old = os.environ.pop("OPS_MCP_ENV_ALLOWLIST", None)
        old_aia = os.environ.pop("AIA_MCP_ENV_ALLOWLIST", None)
        old_extra = os.environ.pop("AIA_MCP_ENV_ALLOWLIST_EXTRA", None)
        old_ops_extra = os.environ.pop("OPS_MCP_ENV_ALLOWLIST_EXTRA", None)
        try:
            keys = mcp_env.mcp_env_allowlist_keys()
            self.assertIn("GOOGLE_OAUTH_CREDENTIALS", keys)
            self.assertIn("BRAVE_API_KEY", keys)
            self.assertIn("GOOGLE_CALENDAR_MCP_TOKEN_PATH", keys)
            self.assertIn("GITHUB_PERSONAL_ACCESS_TOKEN", keys)
            self.assertIn("CONTEXT7_API_KEY", keys)
            self.assertIn("DASHSCOPE_API_KEY", keys)
            self.assertIn("TRILIUM_API_TOKEN", keys)
        finally:
            if old is not None:
                os.environ["OPS_MCP_ENV_ALLOWLIST"] = old
            if old_aia is not None:
                os.environ["AIA_MCP_ENV_ALLOWLIST"] = old_aia
            if old_extra is not None:
                os.environ["AIA_MCP_ENV_ALLOWLIST_EXTRA"] = old_extra
            if old_ops_extra is not None:
                os.environ["OPS_MCP_ENV_ALLOWLIST_EXTRA"] = old_ops_extra

    def test_mcp_env_allowlist_extra_merges_with_default(self) -> None:
        from runtime.operations import mcp_env

        old_aia = os.environ.pop("AIA_MCP_ENV_ALLOWLIST", None)
        old_extra = os.environ.pop("AIA_MCP_ENV_ALLOWLIST_EXTRA", None)
        old_ops_extra = os.environ.pop("OPS_MCP_ENV_ALLOWLIST_EXTRA", None)
        try:
            os.environ["AIA_MCP_ENV_ALLOWLIST_EXTRA"] = "MY_CUSTOM_MCP_SECRET,CONTEXT7_API_KEY"
            keys = mcp_env.mcp_env_allowlist_keys()
            self.assertIn("BRAVE_API_KEY", keys)
            self.assertIn("CONTEXT7_API_KEY", keys)
            self.assertIn("MY_CUSTOM_MCP_SECRET", keys)
            self.assertEqual(keys.index("MY_CUSTOM_MCP_SECRET"), len(keys) - 1)
        finally:
            if old_aia is not None:
                os.environ["AIA_MCP_ENV_ALLOWLIST"] = old_aia
            if old_extra is not None:
                os.environ["AIA_MCP_ENV_ALLOWLIST_EXTRA"] = old_extra
            if old_ops_extra is not None:
                os.environ["OPS_MCP_ENV_ALLOWLIST_EXTRA"] = old_ops_extra

    def test_mcp_env_allowlist_explicit_replace_plus_extra(self) -> None:
        from runtime.operations import mcp_env

        old_aia = os.environ.pop("AIA_MCP_ENV_ALLOWLIST", None)
        old_extra = os.environ.pop("AIA_MCP_ENV_ALLOWLIST_EXTRA", None)
        try:
            os.environ["AIA_MCP_ENV_ALLOWLIST"] = "ONLY_A,ONLY_B"
            os.environ["AIA_MCP_ENV_ALLOWLIST_EXTRA"] = "ONLY_B,ONLY_C"
            keys = mcp_env.mcp_env_allowlist_keys()
            self.assertEqual(keys, ["ONLY_A", "ONLY_B", "ONLY_C"])
            self.assertNotIn("BRAVE_API_KEY", keys)
        finally:
            if old_aia is not None:
                os.environ["AIA_MCP_ENV_ALLOWLIST"] = old_aia
            else:
                os.environ.pop("AIA_MCP_ENV_ALLOWLIST", None)
            if old_extra is not None:
                os.environ["AIA_MCP_ENV_ALLOWLIST_EXTRA"] = old_extra
            else:
                os.environ.pop("AIA_MCP_ENV_ALLOWLIST_EXTRA", None)

    def test_materialize_bailian_webparser_compat_tool(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            store = SqliteStore(str(Path(td) / "ops.sqlite"))
            store.upsert_mcp_server(
                server_id="webparser-compat",
                source_type="npm",
                source_ref="mcp-remote",
                entry_command="npx",
                entry_args=[
                    "-y",
                    "mcp-remote",
                    "https://dashscope.aliyuncs.com/api/v1/mcps/WebParser/sse",
                    "--header",
                    "Authorization: Bearer ${DASHSCOPE_API_KEY}",
                ],
                enabled=True,
            )
            store.replace_mcp_server_tools(
                server_id="webparser-compat",
                tools=[
                    {
                        "tool_name": "bailian_webparser_parse",
                        "description": "compat",
                        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}},
                    }
                ],
            )
            specs = materialize_mcp_tools(store)
            names = {x.name for x in specs}
            self.assertIn("mcp__webparser-compat__bailian_webparser_parse", names)


if __name__ == "__main__":
    unittest.main()

