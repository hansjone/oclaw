from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.tools.mcp.runtime import McpProcessRuntime


class McpRuntimeTests(unittest.TestCase):
    def _write_server(self, body: str) -> str:
        td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(td.cleanup)
        p = Path(td.name) / "mcp_server.py"
        p.write_text(textwrap.dedent(body), encoding="utf-8")
        return str(p)

    def test_health_and_tools_list_jsonrpc(self) -> None:
        script = self._write_server(
            """
            import json
            import sys

            for line in sys.stdin:
                req = json.loads(line)
                rid = req.get("id")
                method = req.get("method")
                if method == "initialize":
                    print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05", "capabilities": {}}}), flush=True)
                    continue
                if method == "notifications/initialized":
                    continue
                if method == "tools/list":
                    print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"tools": [{"name": "ping", "description": "Ping", "inputSchema": {"type": "object", "properties": {}}}]}}), flush=True)
                    continue
                print(json.dumps({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}), flush=True)
            """
        )
        rt = McpProcessRuntime(["python", script], timeout_s=2)
        try:
            health = rt.health()
            self.assertTrue(health.get("ok"))
            self.assertEqual(health.get("status"), "ok")
            tools = rt.tools_list()
            self.assertTrue(tools.get("ok"))
            self.assertTrue(isinstance(tools.get("tools"), list))
        finally:
            rt.stop()

    def test_timeout_returns_error_code(self) -> None:
        script = self._write_server(
            """
            import json
            import sys
            import time

            for line in sys.stdin:
                _ = json.loads(line)
                time.sleep(0.3)
                print(json.dumps({"ok": True}), flush=True)
            """
        )
        rt = McpProcessRuntime(["python", script], timeout_s=0.05)
        try:
            out = rt.request({"op": "health"})
            self.assertFalse(bool(out.get("ok")))
            self.assertEqual(str(out.get("error_code") or ""), "mcp_runtime_timeout")
        finally:
            rt.stop()

    @patch("runtime.operations.mcp_env.mcp_local_env_merged", return_value={"MCP_ONLY_FROM_FILE": "fileval"})
    def test_mcp_local_env_keys_passed_without_allowlist_name(self, _mock_merged: object) -> None:
        os.environ["MCP_ONLY_FROM_FILE"] = "liveval"
        try:
            env = McpProcessRuntime._build_runtime_env([])
            assert env is not None
            self.assertEqual(env.get("MCP_ONLY_FROM_FILE"), "liveval")
        finally:
            os.environ.pop("MCP_ONLY_FROM_FILE", None)

    def test_empty_allowlist_keeps_path_for_subprocess(self) -> None:
        script = self._write_server(
            """
            import json
            import sys

            for line in sys.stdin:
                _ = json.loads(line)
                print(json.dumps({"ok": True, "status": "up"}), flush=True)
            """
        )
        rt = McpProcessRuntime(["python", script], timeout_s=2, env_allowlist=[])
        try:
            out = rt.request({"op": "health"})
            self.assertTrue(bool(out.get("ok")), out)
        finally:
            rt.stop()

    def test_jsonrpc_mcp_flow_tools_and_call(self) -> None:
        script = self._write_server(
            """
            import json
            import sys

            for line in sys.stdin:
                req = json.loads(line)
                rid = req.get("id")
                method = req.get("method")
                if method == "initialize":
                    print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05", "capabilities": {}}}), flush=True)
                    continue
                if method == "notifications/initialized":
                    continue
                if method == "tools/list":
                    print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"tools": [{"name": "ping", "description": "Ping", "inputSchema": {"type": "object", "properties": {}}}]}}), flush=True)
                    continue
                if method == "tools/call":
                    params = req.get("params") or {}
                    args = params.get("arguments") if isinstance(params, dict) else {}
                    print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": str((args or {}).get("msg") or "")}]}}), flush=True)
                    continue
                print(json.dumps({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}), flush=True)
            """
        )
        rt = McpProcessRuntime(["python", script], timeout_s=2)
        try:
            tools = rt.tools_list()
            self.assertTrue(bool(tools.get("ok")), tools)
            self.assertEqual(len(tools.get("tools") or []), 1)
            res = rt.call_tool("ping", {"msg": "hello"})
            self.assertTrue(bool(res.get("ok")), res)
            content = (((res.get("result") or {}).get("content")) or [{}])[0]
            self.assertEqual(str(content.get("text") or ""), "hello")
        finally:
            rt.stop()


if __name__ == "__main__":
    unittest.main()

