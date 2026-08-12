from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from svc.persistence.sqlite_store import SqliteStore
from runtime.tools.mcp.adapter import (
    clear_list_cli_targets_cache,
    materialize_mcp_tools,
    mcp_timeout_for_tool,
)
from runtime.tools.tool_validation import format_invalid_arguments_error, validate_tool_arguments


class McpTimeoutAndCacheTests(unittest.TestCase):
    def test_exec_managed_ne_timeout_override(self) -> None:
        self.assertEqual(mcp_timeout_for_tool("execManagedNe", 30.0), 620.0)
        self.assertEqual(mcp_timeout_for_tool("ping", 30.0), 30.0)
        self.assertGreaterEqual(mcp_timeout_for_tool("sqlQueryUme", 30.0), 90.0)

    def test_materialize_applies_exec_timeout(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            store = SqliteStore(str(Path(td) / "ops.sqlite"))
            store.upsert_mcp_server(
                server_id="netx",
                source_type="github",
                source_ref="local",
                entry_command="python",
                entry_args=["-m", "netx_mcp"],
                enabled=True,
                timeout_s=30.0,
            )
            store.replace_mcp_server_tools(
                server_id="netx",
                tools=[
                    {
                        "tool_name": "execManagedNe",
                        "description": "exec",
                        "parameters": {"type": "object", "properties": {}},
                    },
                    {
                        "tool_name": "listCliTargets",
                        "description": "list",
                        "parameters": {"type": "object", "properties": {}},
                    },
                ],
            )
            specs = {s.name: s for s in materialize_mcp_tools(store)}
            self.assertEqual(specs["mcp__netx__execManagedNe"].timeout_s, 620.0)
            self.assertEqual(specs["mcp__netx__listCliTargets"].timeout_s, 30.0)

    def test_list_cli_targets_ttl_cache(self) -> None:
        clear_list_cli_targets_cache()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            store = SqliteStore(str(Path(td) / "ops.sqlite"))
            store.upsert_mcp_server(
                server_id="netx",
                source_type="github",
                source_ref="local",
                entry_command="python",
                entry_args=["-m", "netx_mcp"],
                enabled=True,
            )
            store.replace_mcp_server_tools(
                server_id="netx",
                tools=[
                    {
                        "tool_name": "listCliTargets",
                        "description": "list",
                        "parameters": {"type": "object", "properties": {}},
                    },
                    {
                        "tool_name": "queryUmeNeInventory",
                        "description": "inventory",
                        "parameters": {"type": "object", "properties": {}},
                    },
                    {
                        "tool_name": "listManagedNe",
                        "description": "managed",
                        "parameters": {"type": "object", "properties": {}},
                    },
                ],
            )
            specs = {s.name: s for s in materialize_mcp_tools(store)}
            calls = {"n": 0}

            def fake_call_tool(self, tool_name, arguments=None):  # type: ignore[no-untyped-def]
                calls["n"] += 1
                return {"ok": True, "data": {"items": [{"ne_id": "1"}], "tool": tool_name}}

            with patch("runtime.tools.mcp.adapter.McpProcessRuntime.call_tool", fake_call_tool):
                cli = specs["mcp__netx__listCliTargets"]
                inv = specs["mcp__netx__queryUmeNeInventory"]
                managed = specs["mcp__netx__listManagedNe"]
                first = cli.handler({"keyword": "PE", "source": "ume"})
                second = cli.handler({"keyword": "PE", "source": "ume"})
                inv1 = inv.handler({"keyword": "core"})
                inv2 = inv.handler({"keyword": "core"})
                m1 = managed.handler({"keyword": "x", "vendor": "huawei", "connect_status": "online"})
                m2 = managed.handler({"keyword": "x", "vendor": "huawei", "connect_status": "online"})
            self.assertEqual(calls["n"], 3)
            self.assertFalse(first.get("cache_hit"))
            self.assertTrue(second.get("cache_hit"))
            self.assertTrue(inv2.get("cache_hit"))
            self.assertTrue(m2.get("cache_hit"))
            self.assertEqual(second.get("data", {}).get("items", [])[0]["ne_id"], "1")
        clear_list_cli_targets_cache()

    def test_alarm_query_ttl_cache(self) -> None:
        clear_list_cli_targets_cache()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            store = SqliteStore(str(Path(td) / "ops.sqlite"))
            store.upsert_mcp_server(
                server_id="netx",
                source_type="github",
                source_ref="local",
                entry_command="python",
                entry_args=["-m", "netx_mcp"],
                enabled=True,
            )
            store.replace_mcp_server_tools(
                server_id="netx",
                tools=[
                    {
                        "tool_name": "queryUmeAlarms",
                        "description": "alarms",
                        "parameters": {"type": "object", "properties": {}},
                    },
                    {
                        "tool_name": "aggregateUmeAlarms",
                        "description": "agg",
                        "parameters": {"type": "object", "properties": {}},
                    },
                    {
                        "tool_name": "runUmeDiagnostics",
                        "description": "diag",
                        "parameters": {"type": "object", "properties": {}},
                    },
                ],
            )
            specs = {s.name: s for s in materialize_mcp_tools(store)}
            calls = {"n": 0}

            def fake_call_tool(self, tool_name, arguments=None):  # type: ignore[no-untyped-def]
                calls["n"] += 1
                return {"ok": True, "data": {"tool": tool_name, "n": calls["n"]}}

            with patch("runtime.tools.mcp.adapter.McpProcessRuntime.call_tool", fake_call_tool):
                q = specs["mcp__netx__queryUmeAlarms"]
                a = specs["mcp__netx__aggregateUmeAlarms"]
                d = specs["mcp__netx__runUmeDiagnostics"]
                q1 = q.handler({"severity": "critical"})
                q2 = q.handler({"severity": "critical"})
                a1 = a.handler({"top_ne": 10})
                a2 = a.handler({"top_ne": 10})
                d1 = d.handler({})
                d2 = d.handler({})
            self.assertEqual(calls["n"], 3)
            self.assertFalse(q1.get("cache_hit"))
            self.assertTrue(q2.get("cache_hit"))
            self.assertTrue(a2.get("cache_hit"))
            self.assertTrue(d2.get("cache_hit"))
            self.assertEqual(a1.get("data", {}).get("tool"), "aggregateUmeAlarms")
            self.assertEqual(d1.get("data", {}).get("tool"), "runUmeDiagnostics")
        clear_list_cli_targets_cache()


class InvalidArgFormatTests(unittest.TestCase):
    def test_format_includes_example(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 30},
            },
            "required": ["command"],
            "additionalProperties": False,
        }
        ok, err = validate_tool_arguments(schema, {})
        self.assertFalse(ok)
        payload = format_invalid_arguments_error(schema, str(err), lang="en")
        self.assertEqual(payload["error_code"], "tool_invalid_arguments")
        self.assertIn("example", payload)
        self.assertIn("command", payload["example"])
        self.assertIn("required", payload)


if __name__ == "__main__":
    unittest.main()
