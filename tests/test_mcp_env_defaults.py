"""MCP subprocess env: env_schema defaults from registry (Cursor mcpServers.env import)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from runtime.tools.mcp.runtime import McpProcessRuntime


class McpEnvDefaultsTests(unittest.TestCase):
    @patch("runtime.operations.mcp_env.mcp_local_env_merged", return_value={})
    def test_env_schema_default_used_when_not_in_os_environ(self, _mock: object) -> None:
        os.environ.pop("NETX_API_URL", None)
        try:
            env = McpProcessRuntime._build_runtime_env(
                ["NETX_API_URL"],
                {"NETX_API_URL": "http://10.0.0.5:8890"},
            )
            assert env is not None
            self.assertEqual(env.get("NETX_API_URL"), "http://10.0.0.5:8890")
        finally:
            pass

    @patch("runtime.operations.mcp_env.mcp_local_env_merged", return_value={})
    def test_mcp_local_and_os_environ_override_schema_default(self, _mock: object) -> None:
        os.environ["NETX_API_URL"] = "http://from-host:8890"
        try:
            env = McpProcessRuntime._build_runtime_env(
                ["NETX_API_URL"],
                {"NETX_API_URL": "http://from-schema:8890"},
            )
            assert env is not None
            self.assertEqual(env.get("NETX_API_URL"), "http://from-host:8890")
        finally:
            os.environ.pop("NETX_API_URL", None)


if __name__ == "__main__":
    unittest.main()
