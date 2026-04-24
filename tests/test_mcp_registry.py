from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.tools.mcp.manifest import McpServerManifest
from oclaw.tools.mcp.registry import McpRegistry


class McpRegistryTests(unittest.TestCase):
    def test_upsert_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            store = SqliteStore(str(Path(td) / "ops.sqlite"))
            reg = McpRegistry(store)
            reg.upsert_manifest(
                McpServerManifest(
                    server_id="demo",
                    source_type="github",
                    source_ref="https://github.com/acme/demo",
                    entry_command="python",
                    entry_args=["-m", "demo"],
                    enabled=True,
                )
            )
            snap = reg.snapshot()
            self.assertEqual(int(snap["count"]), 1)
            self.assertEqual(str(snap["servers"][0]["server_id"]), "demo")


if __name__ == "__main__":
    unittest.main()

