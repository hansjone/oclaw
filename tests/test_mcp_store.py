from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from svc.persistence.sqlite_store import SqliteStore


class McpStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ops.sqlite"
        self.store = SqliteStore(str(self.db))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_upsert_list_and_tools(self) -> None:
        self.store.upsert_mcp_server(
            server_id="s1",
            source_type="github",
            source_ref="https://github.com/acme/mcp-a",
            version="v1",
            entry_command="python",
            entry_args=["-m", "mcp_a"],
            required_permissions=["admin:read"],
            enabled=True,
        )
        self.store.replace_mcp_server_tools(
            server_id="s1",
            tools=[
                {"tool_name": "ping", "description": "Ping tool", "parameters": {"type": "object", "properties": {}}},
            ],
        )
        rows = self.store.list_mcp_servers(enabled_only=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["server_id"], "s1")
        tools = self.store.list_mcp_server_tools(server_id="s1")
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["tool_name"], "ping")

    def test_install_and_health_logs(self) -> None:
        self.store.add_mcp_installation_log(
            server_id="s1",
            status="error",
            error_code="mcp_install_failed",
            detail={"x": 1},
            install_command="npm i -g foo",
        )
        self.store.set_mcp_server_health(server_id="s1", status="ok", detail={"latency_ms": 2})
        logs = self.store.list_mcp_installation_logs(server_id="s1", limit=20)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["error_code"], "mcp_install_failed")
        health = self.store.list_mcp_server_health()
        self.assertEqual(len(health), 1)
        self.assertEqual(health[0]["server_id"], "s1")
        self.store.add_mcp_installation_log(
            server_id="s1",
            status="error",
            error_code="mcp_install_failed",
            detail={},
            install_command="npm i",
        )
        summary = self.store.list_mcp_install_failure_summary(limit=10)
        self.assertTrue(len(summary) >= 1)
        self.assertEqual(summary[0]["server_id"], "s1")
        self.assertEqual(summary[0]["error_code"], "mcp_install_failed")


if __name__ == "__main__":
    unittest.main()

