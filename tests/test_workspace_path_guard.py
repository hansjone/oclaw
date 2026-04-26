from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.config.paths import db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.tools.experts.workspace.fs_tools import list_files_tool, write_file_tool
from oclaw.runtime.tools.experts.workspace.shell_tools import run_command_tool
from oclaw.runtime.tools.experts.workspace.workspace_base import (
    access_from_env,
    build_workspace_path_access,
    clear_workspace_path_access_for_tests,
    current_workspace_write_namespace,
    resolve_workspace_path,
    workspace_path_access_scope,
    workspace_write_namespace_scope,
)


class WorkspacePathGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name) / "ws"
        self.root.mkdir(parents=True)
        self.extra = Path(self._tmp.name) / "outside"
        self.extra.mkdir(parents=True)
        clear_workspace_path_access_for_tests()

    def tearDown(self) -> None:
        clear_workspace_path_access_for_tests()
        self._tmp.cleanup()

    def test_default_only_under_workspace_root(self) -> None:
        inner = self.root / "a" / "b.txt"
        inner.parent.mkdir(parents=True)
        inner.write_text("x", encoding="utf-8")
        with mock.patch.dict(
            os.environ,
            {"OPS_WORKSPACE_ROOT": str(self.root), "OPS_WORKSPACE_EXTRA_ROOTS": "", "OPS_WORKSPACE_ALLOW_ANY_PATH": ""},
            clear=False,
        ):
            with workspace_path_access_scope(None, None):
                p = resolve_workspace_path("a/b.txt")
                self.assertEqual(p, inner.resolve())
                with self.assertRaises(ValueError):
                    resolve_workspace_path(str(self.extra))

    def test_extra_roots_from_env(self) -> None:
        f = self.extra / "f.txt"
        f.write_text("y", encoding="utf-8")
        with mock.patch.dict(
            os.environ,
            {
                "OPS_WORKSPACE_ROOT": str(self.root),
                "OPS_WORKSPACE_EXTRA_ROOTS": str(self.extra),
                "OPS_WORKSPACE_ALLOW_ANY_PATH": "",
            },
            clear=False,
        ):
            with workspace_path_access_scope(None, None):
                p = resolve_workspace_path(str(f))
                self.assertEqual(p, f.resolve())

    def test_glob_tool_accepts_root_parameter(self) -> None:
        sub = self.root / "sub"
        sub.mkdir(parents=True)
        (sub / "a.txt").write_text("a", encoding="utf-8")
        with mock.patch.dict(
            os.environ,
            {"OPS_WORKSPACE_ROOT": str(self.root), "OPS_WORKSPACE_EXTRA_ROOTS": "", "OPS_WORKSPACE_ALLOW_ANY_PATH": ""},
            clear=False,
        ):
            clear_workspace_path_access_for_tests()
            spec = list_files_tool()
            with workspace_path_access_scope(None, None):
                r = spec.handler({"root": str(sub), "pattern": "**/*", "max_results": 50})
            self.assertTrue(r.get("ok"), r)
            self.assertEqual(str(sub.resolve()), str(r.get("root")))
            files = r.get("files") or []
            self.assertTrue(any("a.txt" in f for f in files))

    def test_allow_any_path_from_env(self) -> None:
        f = self.extra / "z.txt"
        f.write_text("z", encoding="utf-8")
        with mock.patch.dict(
            os.environ,
            {
                "OPS_WORKSPACE_ROOT": str(self.root),
                "OPS_WORKSPACE_EXTRA_ROOTS": "",
                "OPS_WORKSPACE_ALLOW_ANY_PATH": "1",
            },
            clear=False,
        ):
            with workspace_path_access_scope(None, None):
                p = resolve_workspace_path(str(f))
                self.assertEqual(p, f.resolve())

    def test_write_file_relative_path_defaults_to_data_workspace_subdir(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"OPS_WORKSPACE_ROOT": str(self.root), "OPS_WORKSPACE_EXTRA_ROOTS": "", "OPS_WORKSPACE_ALLOW_ANY_PATH": ""},
            clear=False,
        ):
            clear_workspace_path_access_for_tests()
            spec = write_file_tool()
            with workspace_path_access_scope(None, None):
                r = spec.handler({"path": "generated.py", "content": "print('ok')\n", "mode": "overwrite"})
            self.assertTrue(r.get("ok"), r)
            expected = (self.root / "data" / "workspace" / "generated.py").resolve()
            self.assertEqual(str(expected), str(r.get("path")))
            self.assertTrue(expected.exists())

    def test_write_file_relative_path_uses_workspace_namespace_scope(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"OPS_WORKSPACE_ROOT": str(self.root), "OPS_WORKSPACE_EXTRA_ROOTS": "", "OPS_WORKSPACE_ALLOW_ANY_PATH": ""},
            clear=False,
        ):
            clear_workspace_path_access_for_tests()
            spec = write_file_tool()
            with workspace_path_access_scope(None, None), workspace_write_namespace_scope("ops"):
                self.assertEqual(current_workspace_write_namespace(), "ops")
                r = spec.handler({"path": "generated.py", "content": "print('ok')\n", "mode": "overwrite"})
            self.assertTrue(r.get("ok"), r)
            expected = (self.root / "data" / "workspace" / "generated.py").resolve()
            self.assertEqual(str(expected), str(r.get("path")))
            self.assertTrue(expected.exists())

    def test_write_file_absolute_path_is_forced_into_workspace_sandbox(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"OPS_WORKSPACE_ROOT": str(self.root), "OPS_WORKSPACE_EXTRA_ROOTS": "", "OPS_WORKSPACE_ALLOW_ANY_PATH": ""},
            clear=False,
        ):
            clear_workspace_path_access_for_tests()
            spec = write_file_tool()
            abs_target = str((self.root / "count_items.py").resolve())
            with workspace_path_access_scope(None, None), workspace_write_namespace_scope("ops"):
                r = spec.handler({"path": abs_target, "content": "print('ok')\n", "mode": "overwrite"})
            self.assertTrue(r.get("ok"), r)
            expected = (self.root / "data" / "workspace" / "count_items.py").resolve()
            self.assertEqual(str(expected), str(r.get("path")))
            self.assertTrue(expected.exists())

    def test_run_command_default_cwd_uses_workspace_namespace_sandbox(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "OPS_WORKSPACE_ROOT": str(self.root),
                "OPS_WORKSPACE_EXTRA_ROOTS": "",
                "OPS_WORKSPACE_ALLOW_ANY_PATH": "",
                "AIA_ENABLE_RUN_COMMAND": "1",
            },
            clear=False,
        ):
            clear_workspace_path_access_for_tests()
            spec = run_command_tool()
            with workspace_path_access_scope(None, None), workspace_write_namespace_scope("ops"):
                r = spec.handler({"command": "python -c \"print('ok')\""})
            self.assertTrue(r.get("ok"), r)
            expected_cwd = (self.root / "data" / "workspace").resolve()
            self.assertEqual(str(expected_cwd), str(r.get("cwd")))

    def test_run_command_strips_leading_cd_chain_in_default_sandbox(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "OPS_WORKSPACE_ROOT": str(self.root),
                "OPS_WORKSPACE_EXTRA_ROOTS": "",
                "OPS_WORKSPACE_ALLOW_ANY_PATH": "",
                "AIA_ENABLE_RUN_COMMAND": "1",
            },
            clear=False,
        ):
            clear_workspace_path_access_for_tests()
            spec = run_command_tool()
            cmd = f'cd /d "{self.root}" && python -c "print(123)"'
            with workspace_path_access_scope(None, None), workspace_write_namespace_scope("ops"):
                r = spec.handler({"command": cmd})
            self.assertTrue(r.get("ok"), r)
            self.assertTrue(bool(r.get("normalized_cd_removed")))
            expected_cwd = (self.root / "data" / "workspace").resolve()
            self.assertEqual(str(expected_cwd), str(r.get("cwd")))
            self.assertIn("123", str(r.get("output") or ""))

    def test_run_command_strips_windows_drive_prefix_cd_chain(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "OPS_WORKSPACE_ROOT": str(self.root),
                "OPS_WORKSPACE_EXTRA_ROOTS": "",
                "OPS_WORKSPACE_ALLOW_ANY_PATH": "",
                "AIA_ENABLE_RUN_COMMAND": "1",
            },
            clear=False,
        ):
            clear_workspace_path_access_for_tests()
            ws_root = self.root / "data" / "workspace"
            ws_root.mkdir(parents=True, exist_ok=True)
            (ws_root / "count_directory.py").write_text("print('drive-cd-ok')\n", encoding="utf-8")
            spec = run_command_tool()
            cmd = f'D: && cd /d "{self.root}" && python count_directory.py'
            with workspace_path_access_scope(None, None):
                r = spec.handler({"command": cmd})
            self.assertTrue(r.get("ok"), r)
            self.assertTrue(bool(r.get("normalized_cd_removed")), r)
            self.assertTrue(bool(r.get("script_path_rewritten")), r)
            self.assertIn("drive-cd-ok", str(r.get("output") or ""))

    def test_run_command_output_flags_distinguish_empty_from_truncation(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "OPS_WORKSPACE_ROOT": str(self.root),
                "OPS_WORKSPACE_EXTRA_ROOTS": "",
                "OPS_WORKSPACE_ALLOW_ANY_PATH": "",
                "AIA_ENABLE_RUN_COMMAND": "1",
            },
            clear=False,
        ):
            clear_workspace_path_access_for_tests()
            spec = run_command_tool()
            with workspace_path_access_scope(None, None), workspace_write_namespace_scope("ops"):
                r = spec.handler({"command": 'python -c "pass"'})
            self.assertTrue(r.get("ok"), r)
            self.assertTrue(bool(r.get("output_empty")))
            self.assertFalse(bool(r.get("output_truncated")))
            self.assertTrue(bool(r.get("output_not_truncated")))
            self.assertEqual(str(r.get("error_code") or ""), "")

    def test_run_command_nonzero_exit_marks_failure_not_truncation(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "OPS_WORKSPACE_ROOT": str(self.root),
                "OPS_WORKSPACE_EXTRA_ROOTS": "",
                "OPS_WORKSPACE_ALLOW_ANY_PATH": "",
                "AIA_ENABLE_RUN_COMMAND": "1",
            },
            clear=False,
        ):
            clear_workspace_path_access_for_tests()
            spec = run_command_tool()
            with workspace_path_access_scope(None, None), workspace_write_namespace_scope("ops"):
                r = spec.handler({"command": 'python -c "import sys; sys.exit(3)"'})
            self.assertFalse(bool(r.get("ok")))
            self.assertEqual(int(r.get("exit_code") or 0), 3)
            self.assertEqual(str(r.get("error_code") or ""), "command_exit_nonzero")
            self.assertFalse(bool(r.get("output_truncated")))

    def test_run_command_rewrites_workspace_absolute_script_path_to_sandbox(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "OPS_WORKSPACE_ROOT": str(self.root),
                "OPS_WORKSPACE_EXTRA_ROOTS": "",
                "OPS_WORKSPACE_ALLOW_ANY_PATH": "",
                "AIA_ENABLE_RUN_COMMAND": "1",
            },
            clear=False,
        ):
            clear_workspace_path_access_for_tests()
            # Prepare script inside sandbox, but command will reference repo-root absolute path.
            ws_script = self.root / "data" / "workspace" / "count_files.py"
            ws_script.parent.mkdir(parents=True, exist_ok=True)
            ws_script.write_text("print('sandbox-ok')\n", encoding="utf-8")
            spec = run_command_tool()
            absolute_repo_script = str((self.root / "count_files.py").resolve())
            with workspace_path_access_scope(None, None), workspace_write_namespace_scope("ops"):
                r = spec.handler({"command": f'python "{absolute_repo_script}"'})
            self.assertTrue(r.get("ok"), r)
            self.assertTrue(bool(r.get("command_rewritten")), r)
            self.assertIn("sandbox-ok", str(r.get("output") or ""))

    def test_run_command_explicit_repo_root_cwd_is_redirected_to_sandbox(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "OPS_WORKSPACE_ROOT": str(self.root),
                "OPS_WORKSPACE_EXTRA_ROOTS": "",
                "OPS_WORKSPACE_ALLOW_ANY_PATH": "",
                "AIA_ENABLE_RUN_COMMAND": "1",
            },
            clear=False,
        ):
            clear_workspace_path_access_for_tests()
            ws_script = self.root / "data" / "workspace" / "count_files.py"
            ws_script.parent.mkdir(parents=True, exist_ok=True)
            ws_script.write_text("print('redirect-ok')\n", encoding="utf-8")
            spec = run_command_tool()
            abs_repo_script = str((self.root / "count_files.py").resolve())
            with workspace_path_access_scope(None, None):
                r = spec.handler(
                    {
                        "command": f'python "{abs_repo_script}"',
                        "cwd": str(self.root),
                    }
                )
            self.assertTrue(r.get("ok"), r)
            self.assertTrue(bool(r.get("cwd_redirected_to_sandbox")), r)
            self.assertTrue(bool(r.get("command_rewritten")), r)
            self.assertIn("redirect-ok", str(r.get("output") or ""))

    def test_run_command_rewrites_relative_python_script_to_sandbox_root(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "OPS_WORKSPACE_ROOT": str(self.root),
                "OPS_WORKSPACE_EXTRA_ROOTS": "",
                "OPS_WORKSPACE_ALLOW_ANY_PATH": "",
                "AIA_ENABLE_RUN_COMMAND": "1",
            },
            clear=False,
        ):
            clear_workspace_path_access_for_tests()
            ws_root = self.root / "data" / "workspace"
            ws_root.mkdir(parents=True, exist_ok=True)
            (ws_root / "count_directory.py").write_text("print('found-in-sandbox-root')\n", encoding="utf-8")
            spec = run_command_tool()
            with workspace_path_access_scope(None, None):
                r = spec.handler({"command": "python count_directory.py"})
            self.assertTrue(r.get("ok"), r)
            self.assertTrue(bool(r.get("script_path_rewritten")), r)
            self.assertIn("found-in-sandbox-root", str(r.get("output") or ""))

    def test_per_user_extra_roots_from_db(self) -> None:
        f = self.extra / "u.txt"
        f.write_text("u", encoding="utf-8")
        dbf = Path(self._tmp.name) / "ops.sqlite"
        store = SqliteStore(str(dbf))
        t = store.create_tenant("T")
        tid = str(t["id"])
        u = store.create_user_account(
            tenant_id=tid,
            username="u1",
            display_name="U1",
            role="member",
            password_hash=hashlib.sha256(b"x").hexdigest(),
            is_active=True,
        )
        uid = str(u["id"])
        sess = store.create_session("s")
        sid = str(sess.id)
        store.ensure_ui_session_owner(session_id=sid, tenant_id=tid, user_id=uid)
        store.upsert_user_workspace_path_allowlist(
            tenant_id=tid,
            user_id=uid,
            extra_roots=str(self.extra),
            allow_any_path=False,
        )
        with mock.patch.dict(
            os.environ,
            {"OPS_WORKSPACE_ROOT": str(self.root), "OPS_WORKSPACE_EXTRA_ROOTS": "", "OPS_WORKSPACE_ALLOW_ANY_PATH": ""},
            clear=False,
        ):
            acc = build_workspace_path_access(store, sid)
            self.assertIn(self.extra.resolve(), [p.resolve() for p in acc.extra_roots])
            with workspace_path_access_scope(store, sid):
                p = resolve_workspace_path(str(f))
                self.assertEqual(p, f.resolve())

    def test_extra_roots_use_ui_owner_fallback_when_tool_session_is_unowned(self) -> None:
        """Specialist steps use a temp chat_session without ui_session_owner; allowlist must follow user session."""
        f = self.extra / "orphan.txt"
        f.write_text("x", encoding="utf-8")
        dbf = Path(self._tmp.name) / "ops2.sqlite"
        store = SqliteStore(str(dbf))
        t = store.create_tenant("T2")
        tid = str(t["id"])
        u = store.create_user_account(
            tenant_id=tid,
            username="u2",
            display_name="U2",
            role="member",
            password_hash=hashlib.sha256(b"z").hexdigest(),
            is_active=True,
        )
        uid = str(u["id"])
        user_sess = store.create_session_for_user(title="ui", tenant_id=tid, user_id=uid)
        user_sid = str(user_sess.id)
        temp_sess = store.create_session("specialist:generalist")
        temp_sid = str(temp_sess.id)
        store.upsert_user_workspace_path_allowlist(
            tenant_id=tid,
            user_id=uid,
            extra_roots=str(self.extra),
            allow_any_path=False,
        )
        with mock.patch.dict(
            os.environ,
            {"OPS_WORKSPACE_ROOT": str(self.root), "OPS_WORKSPACE_EXTRA_ROOTS": "", "OPS_WORKSPACE_ALLOW_ANY_PATH": ""},
            clear=False,
        ):
            acc = build_workspace_path_access(store, temp_sid)
            roots_no_fb = [p.resolve() for p in acc.extra_roots]
            self.assertNotIn(self.extra.resolve(), roots_no_fb)
            acc2 = build_workspace_path_access(store, temp_sid, owner_fallback_session_id=user_sid)
            self.assertIn(self.extra.resolve(), [p.resolve() for p in acc2.extra_roots])
            with workspace_path_access_scope(store, temp_sid, owner_fallback_session_id=user_sid):
                p = resolve_workspace_path(str(f))
                self.assertEqual(p, f.resolve())


class WorkspacePathPolicyAdminApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ops.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["OPS_ASSISTANT_PASSWORD"] = "test-admin-pass"
        store = SqliteStore(str(self.db))
        t = store.create_tenant("Team")
        self.tenant_id = str(t["id"])
        store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash=hashlib.sha256("test-admin-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.target = store.create_user_account(
            tenant_id=self.tenant_id,
            username="member1",
            display_name="M1",
            role="member",
            password_hash=hashlib.sha256(b"y").hexdigest(),
            is_active=True,
        )
        self.client = TestClient(create_app())
        self.client.post("/admin/api/auth/bootstrap", json={})
        self.token = self._login()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _headers(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}"}

    def _login(self) -> str:
        resp = self.client.post(
            "/admin/api/auth/login",
            json={
                "tenant_id": self.tenant_id,
                "username": "administrator",
                "password": "test-admin-pass",
                "purpose": "console",
            },
        )
        data = resp.json()
        self.assertTrue(data.get("ok"), data)
        return str(data.get("token") or "")

    def test_get_post_workspace_path_policy(self) -> None:
        uid = str(self.target.get("id") or "")
        g = self.client.get(
            f"/admin/api/users/workspace-path-policy?tenant_id={self.tenant_id}&user_id={uid}",
            headers=self._headers(),
        )
        self.assertEqual(g.status_code, 200)
        self.assertTrue(g.json().get("ok"))
        self.assertFalse(g.json().get("from_db"))

        p = Path(self._tmp.name) / "allowed_side"
        p.mkdir(parents=True)
        resp = self.client.post(
            "/admin/api/users/workspace-path-policy",
            json={
                "tenant_id": self.tenant_id,
                "user_id": uid,
                "extra_roots": str(p),
                "allow_any_path": False,
            },
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("ok"), resp.json())
        g2 = self.client.get(
            f"/admin/api/users/workspace-path-policy?tenant_id={self.tenant_id}&user_id={uid}",
            headers=self._headers(),
        )
        data = g2.json()
        self.assertTrue(data.get("from_db"))
        self.assertIn(str(p.resolve()), str((data.get("policy") or {}).get("extra_roots") or ""))

    def test_member_workspace_path_policy_self_only(self) -> None:
        store = SqliteStore(str(self.db))
        mem = store.create_user_account(
            tenant_id=self.tenant_id,
            username="pathmember",
            display_name="Path Member",
            role="member",
            password_hash=hashlib.sha256(b"mem-pass").hexdigest(),
            is_active=True,
        )
        mid = str(mem.get("id") or "")
        resp = self.client.post(
            "/admin/api/auth/login",
            json={
                "tenant_id": self.tenant_id,
                "username": "pathmember",
                "password": "mem-pass",
                "purpose": "console",
            },
        )
        self.assertEqual(resp.status_code, 200)
        tok = str(resp.json().get("token") or "")
        self.assertTrue(tok)
        h = {"authorization": f"Bearer {tok}"}
        g = self.client.get(
            f"/admin/api/users/workspace-path-policy?tenant_id={self.tenant_id}&user_id={mid}",
            headers=h,
        )
        self.assertEqual(g.status_code, 200)
        self.assertTrue(g.json().get("ok"))
        g2 = self.client.get(
            f"/admin/api/users/workspace-path-policy?tenant_id={self.tenant_id}&user_id=wrong-user-id",
            headers=h,
        )
        self.assertEqual(g2.status_code, 403)


if __name__ == "__main__":
    unittest.main()
