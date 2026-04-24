from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.tools.mcp.filesystem_argv import augment_filesystem_mcp_argv, build_mcp_process_command


def _wincase_set(items: list[str]) -> set[str]:
    if os.name == "nt":
        return {os.path.normcase(x) for x in items}
    return set(items)


class McpFilesystemArgvTests(unittest.TestCase):
    def test_non_filesystem_unchanged(self) -> None:
        cmd = ["python", "-c", "print(1)"]
        self.assertEqual(augment_filesystem_mcp_argv(cmd, store=None), cmd)

    def test_appends_extra_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            extra = tmp / "extra_side"
            extra.mkdir()
            base_cmd = ["npx", "-y", "@modelcontextprotocol/server-filesystem", str(tmp)]
            with mock.patch.dict(os.environ, {"OPS_WORKSPACE_EXTRA_ROOTS": str(extra)}, clear=False):
                out = augment_filesystem_mcp_argv(list(base_cmd), store=None)
            self.assertGreater(len(out), len(base_cmd))
            sset = _wincase_set(out)
            self.assertIn(os.path.normcase(str(extra.resolve())), sset)

    def test_build_mcp_process_command(self) -> None:
        out = build_mcp_process_command("echo", ["a"], store=None)
        self.assertEqual(out, ["echo", "a"])

    def test_policy_session_only_that_users_db_roots(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            dbf = Path(td) / "ops.sqlite"
            store = SqliteStore(str(dbf))
            t = store.create_tenant("T")
            tid = str(t["id"])
            ua = store.create_user_account(
                tenant_id=tid,
                username="ua",
                display_name="A",
                role="member",
                password_hash=hashlib.sha256(b"a").hexdigest(),
                is_active=True,
            )
            ub = store.create_user_account(
                tenant_id=tid,
                username="ub",
                display_name="B",
                role="member",
                password_hash=hashlib.sha256(b"b").hexdigest(),
                is_active=True,
            )
            sa = store.create_session("sa")
            sb = store.create_session("sb")
            store.ensure_ui_session_owner(session_id=str(sa.id), tenant_id=tid, user_id=str(ua["id"]))
            store.ensure_ui_session_owner(session_id=str(sb.id), tenant_id=tid, user_id=str(ub["id"]))
            root = Path(td) / "fsroot"
            root.mkdir()
            pa = root / "a_only"
            pa.mkdir()
            pb = root / "b_only"
            pb.mkdir()
            store.upsert_user_workspace_path_allowlist(
                tenant_id=tid, user_id=str(ua["id"]), extra_roots=str(pa), allow_any_path=False
            )
            store.upsert_user_workspace_path_allowlist(
                tenant_id=tid, user_id=str(ub["id"]), extra_roots=str(pb), allow_any_path=False
            )
            base = ["npx", "-y", "@modelcontextprotocol/server-filesystem", str(root)]
            out_a = augment_filesystem_mcp_argv(list(base), store=store, policy_session_id=str(sa.id))
            out_b = augment_filesystem_mcp_argv(list(base), store=store, policy_session_id=str(sb.id))
            a_set, b_set = _wincase_set(out_a), _wincase_set(out_b)
            self.assertIn(os.path.normcase(str(pa.resolve())), a_set)
            self.assertNotIn(os.path.normcase(str(pb.resolve())), a_set)
            self.assertIn(os.path.normcase(str(pb.resolve())), b_set)
            self.assertNotIn(os.path.normcase(str(pa.resolve())), b_set)
            del store


if __name__ == "__main__":
    unittest.main()
