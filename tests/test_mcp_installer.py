from __future__ import annotations

import unittest

from runtime.tools.mcp.installer import (
    _safe_server_id,
    detect_local_dependencies,
    install_mcp_server,
    preflight_mcp_server,
    uninstall_mcp_server,
)
from runtime.tools.mcp.manifest import McpServerManifest


class McpInstallerTests(unittest.TestCase):
    def test_safe_server_id(self) -> None:
        self.assertEqual(_safe_server_id("Hello World/Repo"), "hello-world-repo")

    def test_install_dry_run(self) -> None:
        m = McpServerManifest(server_id="x", source_type="npm", source_ref="demo-server", version="1.0.0")
        res = install_mcp_server(m, dry_run=True)
        self.assertTrue(res.ok)
        self.assertIn(" install -g ", res.install_command)
        self.assertIn("demo-server@1.0.0", res.install_command)

    def test_install_local_skips_package_step(self) -> None:
        m = McpServerManifest(server_id="netx", source_type="local", source_ref="netx-mcp-http", entry_command="python")
        res = install_mcp_server(m, dry_run=False)
        self.assertTrue(res.ok)
        self.assertEqual(res.install_command, "")
        self.assertEqual((res.details or {}).get("reason"), "local_source_no_package_install")

    def test_invalid_source(self) -> None:
        m = McpServerManifest(server_id="x", source_type="invalid", source_ref="x")
        res = install_mcp_server(m, dry_run=True)
        self.assertFalse(res.ok)
        self.assertEqual(res.error_code, "mcp_invalid_source")

    def test_uninstall_dry_run(self) -> None:
        m = McpServerManifest(server_id="x", source_type="npm", source_ref="demo-server")
        res = uninstall_mcp_server(m, dry_run=True)
        self.assertTrue(res.ok)
        self.assertIn(" uninstall -g ", res.install_command)

    def test_preflight_missing_entry(self) -> None:
        m = McpServerManifest(server_id="x", source_type="npm", source_ref="demo", entry_command="")
        res = preflight_mcp_server(m)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error_code"], "mcp_entry_missing")
        self.assertTrue(isinstance(res.get("fix_suggestions"), list))

    def test_detect_local_dependencies_shape(self) -> None:
        rows = detect_local_dependencies()
        self.assertTrue(isinstance(rows, list))
        self.assertTrue(all(isinstance(x, dict) for x in rows))


if __name__ == "__main__":
    unittest.main()

