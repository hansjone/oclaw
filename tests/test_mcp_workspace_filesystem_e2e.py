"""End-to-end style checks: DB allowlist → MCP server-filesystem argv augmentation.

Reproduces the case where the primary argv root is the repo (D:) while ``extra_roots``
must be merged so ``list_directory`` on e.g. Desktop is allowed by the MCP subprocess.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from oclaw.runtime.agents.network_ops_agent import NetworkOpsAgent
from oclaw.platform.llm.chat_models import RuleBasedChatModel
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.tools.mcp.adapter import materialize_mcp_tools_for_specialist
from oclaw.runtime.tools.mcp.filesystem_argv import build_mcp_process_command, collect_filesystem_mcp_extra_roots
from oclaw.runtime.tools.mcp.runtime import McpProcessRuntime


class McpWorkspaceFilesystemE2ETests(unittest.TestCase):
    def test_collect_merges_allowlist_distinct_from_project_root(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            dbf = Path(td) / "ops.sqlite"
            store = SqliteStore(str(dbf))
            t = store.create_tenant("T")
            tid = str(t["id"])
            u = store.create_user_account(
                tenant_id=tid,
                username="u1",
                display_name="U",
                role="member",
                password_hash=hashlib.sha256(b"x").hexdigest(),
                is_active=True,
            )
            uid = str(u["id"])
            sess = store.create_session("chat")
            store.ensure_ui_session_owner(session_id=str(sess.id), tenant_id=tid, user_id=uid)
            extra = Path(td) / "extra_outside_project"
            extra.mkdir()
            store.upsert_user_workspace_path_allowlist(
                tenant_id=tid,
                user_id=uid,
                extra_roots=str(extra),
                allow_any_path=False,
            )
            roots = collect_filesystem_mcp_extra_roots(
                store=store,
                policy_session_id=str(sess.id),
                path_policy_tenant_id=tid,
                path_policy_user_id=uid,
            )
            keys = {os.path.normcase(x) for x in roots}
            self.assertIn(os.path.normcase(str(extra.resolve())), keys)

    def test_build_mcp_process_command_appends_extra_root_to_npx_filesystem(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            dbf = Path(td) / "ops.sqlite"
            store = SqliteStore(str(dbf))
            t = store.create_tenant("T2")
            tid = str(t["id"])
            u = store.create_user_account(
                tenant_id=tid,
                username="u2",
                display_name="U2",
                role="member",
                password_hash=hashlib.sha256(b"y").hexdigest(),
                is_active=True,
            )
            uid = str(u["id"])
            sess = store.create_session("c2")
            store.ensure_ui_session_owner(session_id=str(sess.id), tenant_id=tid, user_id=uid)
            proj = Path(td) / "repo"
            proj.mkdir()
            extra = Path(td) / "allowed_extra"
            extra.mkdir()
            store.upsert_user_workspace_path_allowlist(
                tenant_id=tid,
                user_id=uid,
                extra_roots=str(extra),
                allow_any_path=False,
            )
            cmd = build_mcp_process_command(
                "npx",
                ["-y", "@modelcontextprotocol/server-filesystem", str(proj)],
                store=store,
                policy_session_id=str(sess.id),
                path_policy_tenant_id=tid,
                path_policy_user_id=uid,
            )
            norm = {os.path.normcase(x) for x in cmd}
            self.assertIn(os.path.normcase(str(extra.resolve())), norm)
            self.assertGreaterEqual(len([x for x in cmd if os.path.normcase(x) == os.path.normcase(str(extra.resolve()))]), 1)

    def test_materialize_mcp_includes_augmented_argv_for_filesystem(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            dbf = Path(td) / "ops.sqlite"
            store = SqliteStore(str(dbf))
            t = store.create_tenant("T3")
            tid = str(t["id"])
            u = store.create_user_account(
                tenant_id=tid,
                username="u3",
                display_name="U3",
                role="member",
                password_hash=hashlib.sha256(b"z").hexdigest(),
                is_active=True,
            )
            uid = str(u["id"])
            sess = store.create_session("c3")
            store.ensure_ui_session_owner(session_id=str(sess.id), tenant_id=tid, user_id=uid)
            proj = Path(td) / "wroot"
            proj.mkdir()
            extra = Path(td) / "mcp_extra"
            extra.mkdir()
            store.upsert_user_workspace_path_allowlist(
                tenant_id=tid,
                user_id=uid,
                extra_roots=str(extra),
                allow_any_path=False,
            )
            store.upsert_mcp_server(
                server_id="mcp-server-filesystem",
                source_type="npm",
                source_ref="@modelcontextprotocol/server-filesystem",
                version="",
                entry_command="npx",
                entry_args=["-y", "@modelcontextprotocol/server-filesystem", str(proj)],
                env_schema={},
                required_permissions=[],
                risk_level="high",
                timeout_s=60.0,
                enabled=True,
            )
            store.replace_mcp_server_tools(
                server_id="mcp-server-filesystem",
                tools=[
                    {
                        "tool_name": "list_directory",
                        "description": "list",
                        "parameters": {"type": "object", "properties": {}},
                    }
                ],
            )
            tools = materialize_mcp_tools_for_specialist(
                store,
                specialist="generalist",
                policy_session_id=str(sess.id),
                path_policy_tenant_id=tid,
                path_policy_user_id=uid,
            )
            fs = [x for x in tools if "mcp__mcp-server-filesystem__" in (x.name or "")]
            self.assertTrue(fs, msg="expected filesystem MCP tools")
            rebuilt = build_mcp_process_command(
                "npx",
                ["-y", "@modelcontextprotocol/server-filesystem", str(proj)],
                store=store,
                policy_session_id=str(sess.id),
                path_policy_tenant_id=tid,
                path_policy_user_id=uid,
            )
            self.assertIn(os.path.normcase(str(extra.resolve())), {os.path.normcase(x) for x in rebuilt})

    def test_network_ops_agent_mcp_filesystem_argv_includes_user_extra_roots(self) -> None:
        """Ops specialist uses NetworkOpsAgent; it must still merge per-user extra_roots into MCP argv."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            dbf = Path(td) / "ops.sqlite"
            store = SqliteStore(str(dbf))
            t = store.create_tenant("T4")
            tid = str(t["id"])
            u = store.create_user_account(
                tenant_id=tid,
                username="u4",
                display_name="U4",
                role="member",
                password_hash=hashlib.sha256(b"w").hexdigest(),
                is_active=True,
            )
            uid = str(u["id"])
            sess = store.create_session("c4")
            store.ensure_ui_session_owner(session_id=str(sess.id), tenant_id=tid, user_id=uid)
            proj = Path(td) / "ops_wroot"
            proj.mkdir()
            extra = Path(td) / "ops_mcp_extra"
            extra.mkdir()
            store.upsert_user_workspace_path_allowlist(
                tenant_id=tid,
                user_id=uid,
                extra_roots=str(extra),
                allow_any_path=False,
            )
            store.upsert_mcp_server(
                server_id="mcp-server-filesystem",
                source_type="npm",
                source_ref="@modelcontextprotocol/server-filesystem",
                version="",
                entry_command="npx",
                entry_args=["-y", "@modelcontextprotocol/server-filesystem", str(proj)],
                env_schema={},
                required_permissions=[],
                risk_level="high",
                timeout_s=60.0,
                enabled=True,
            )
            store.replace_mcp_server_tools(
                server_id="mcp-server-filesystem",
                tools=[
                    {
                        "tool_name": "list_directory",
                        "description": "list",
                        "parameters": {"type": "object", "properties": {}},
                    }
                ],
            )
            agent = NetworkOpsAgent(
                store=store,
                model=RuleBasedChatModel(),
                policy_session_id=str(sess.id),
                path_policy_tenant_id=tid,
                path_policy_user_id=uid,
            )
            fs_tools = [x for x in agent.tools.list() if "mcp__mcp-server-filesystem__" in (x.name or "")]
            self.assertTrue(fs_tools, msg="expected filesystem MCP tools on NetworkOpsAgent")
            h = fs_tools[0].handler
            rt = None
            for cell in getattr(h, "__closure__", None) or ():
                v = cell.cell_contents
                if isinstance(v, McpProcessRuntime):
                    rt = v
                    break
            self.assertIsNotNone(rt)
            assert rt is not None
            cmd = list(rt.command)
            self.assertIn(os.path.normcase(str(extra.resolve())), {os.path.normcase(x) for x in cmd})


if __name__ == "__main__":
    unittest.main()
