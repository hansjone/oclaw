from __future__ import annotations

import hashlib
import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.interfaces.admin import routes as admin_routes
from oclaw.platform.config.paths import db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore


class McpAdminApiTests(unittest.TestCase):
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
            json={"tenant_id": self.tenant_id, "username": "administrator", "password": "test-admin-pass", "purpose": "console"},
        )
        data = resp.json()
        self.assertTrue(data.get("ok"), data)
        return str(data.get("token") or "")

    def _write_mcp_server(self) -> str:
        p = Path(self._tmp.name) / "dummy_mcp_server.py"
        p.write_text(
            textwrap.dedent(
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
                        print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"tools": [{"name": "ping", "description": "Ping", "inputSchema": {"type": "object"}}]}}), flush=True)
                        continue
                    if method == "tools/call":
                        print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": "pong"}]}}), flush=True)
                        continue
                    print(json.dumps({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}), flush=True)
                """
            ),
            encoding="utf-8",
        )
        return str(p)

    def test_install_toggle_and_failure_summary(self) -> None:
        pre = self.client.post(
            "/admin/api/mcp/preflight",
            json={"source_type": "npm", "source_ref": "demo-mcp", "entry_command": "python", "entry_args": ["-V"]},
            headers=self._headers(),
        )
        self.assertEqual(pre.status_code, 200)
        self.assertTrue(pre.json().get("ok"))

        ins = self.client.post(
            "/admin/api/mcp/install",
            json={"source_type": "npm", "source_ref": "demo-mcp", "server_id": "demo-mcp", "entry_command": "python", "entry_args": ["-V"], "dry_run": True},
            headers=self._headers(),
        )
        self.assertEqual(ins.status_code, 200)
        self.assertTrue(ins.json().get("ok"), ins.json())

        toggle = self.client.post(
            "/admin/api/mcp/toggle",
            json={"server_id": "demo-mcp", "enabled": True},
            headers=self._headers(),
        )
        self.assertEqual(toggle.status_code, 200)
        self.assertTrue(toggle.json().get("ok"))

        store = SqliteStore(db_path())
        store.add_mcp_installation_log(
            server_id="demo-mcp",
            status="error",
            error_code="mcp_install_failed",
            detail={"error": "boom"},
            install_command="npm install -g demo-mcp",
        )
        failures = self.client.get("/admin/api/mcp/failures?limit=20", headers=self._headers())
        self.assertEqual(failures.status_code, 200)
        items = failures.json().get("items") or []
        self.assertTrue(any(str(x.get("server_id") or "") == "demo-mcp" for x in items))

    def test_healthcheck_and_tools_sync(self) -> None:
        script = self._write_mcp_server()
        store = SqliteStore(db_path())
        store.upsert_mcp_server(
            server_id="dummy",
            source_type="github",
            source_ref="https://example.com/repo.git",
            entry_command="python",
            entry_args=[script],
            enabled=True,
        )
        health = self.client.post("/admin/api/mcp/healthcheck", json={"server_id": "dummy"}, headers=self._headers())
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json().get("ok"), health.json())

        sync = self.client.post("/admin/api/mcp/tools/sync", json={"server_id": "dummy"}, headers=self._headers())
        self.assertEqual(sync.status_code, 200)
        self.assertTrue(sync.json().get("ok"), sync.json())
        tools = sync.json().get("tools") or []
        self.assertTrue(any(str(t.get("tool_name") or "") == "ping" for t in tools))

    def test_healthcheck_and_tools_sync_bailian_webparser_compat(self) -> None:
        store = SqliteStore(db_path())
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
        health = self.client.post("/admin/api/mcp/healthcheck", json={"server_id": "webparser-compat"}, headers=self._headers())
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json().get("ok"), health.json())
        self.assertEqual(str((health.json().get("response") or {}).get("compat_mode") or ""), "bailian_webparser")

        sync = self.client.post("/admin/api/mcp/tools/sync", json={"server_id": "webparser-compat"}, headers=self._headers())
        self.assertEqual(sync.status_code, 200)
        self.assertTrue(sync.json().get("ok"), sync.json())
        tools = sync.json().get("tools") or []
        self.assertTrue(any(str(t.get("tool_name") or "") == "bailian_webparser_parse" for t in tools))

    def test_reinstall_from_saved_manifest(self) -> None:
        script = self._write_mcp_server()
        store = SqliteStore(db_path())
        store.upsert_mcp_server(
            server_id="dummy-reinstall",
            source_type="npm",
            source_ref="mcp-fetch-server",
            entry_command="python",
            entry_args=[script],
            enabled=True,
        )
        resp = self.client.post(
            "/admin/api/mcp/reinstall",
            json={"server_id": "dummy-reinstall", "dry_run": True},
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"), data)
        self.assertEqual(str(data.get("server_id") or ""), "dummy-reinstall")

    def test_update_from_saved_manifest_single_and_batch(self) -> None:
        script = self._write_mcp_server()
        store = SqliteStore(db_path())
        store.upsert_mcp_server(
            server_id="dummy-update",
            source_type="npm",
            source_ref="mcp-fetch-server",
            entry_command="python",
            entry_args=[script],
            enabled=True,
        )
        single = self.client.post(
            "/admin/api/mcp/update",
            json={"server_id": "dummy-update", "dry_run": True, "update_to_latest": True},
            headers=self._headers(),
        )
        self.assertEqual(single.status_code, 200)
        d1 = single.json()
        self.assertTrue(d1.get("ok"), d1)
        self.assertEqual(int(d1.get("total") or 0), 1)
        self.assertEqual(str((d1.get("items") or [{}])[0].get("server_id") or ""), "dummy-update")

        batch = self.client.post(
            "/admin/api/mcp/update",
            json={"enabled_only": True, "dry_run": True, "update_to_latest": True},
            headers=self._headers(),
        )
        self.assertEqual(batch.status_code, 200)
        d2 = batch.json()
        self.assertTrue(d2.get("ok"), d2)
        self.assertGreaterEqual(int(d2.get("total") or 0), 1)

    def test_check_all_enabled_servers(self) -> None:
        script = self._write_mcp_server()
        store = SqliteStore(db_path())
        store.upsert_mcp_server(
            server_id="dummy-check-all",
            source_type="github",
            source_ref="https://example.com/repo.git",
            entry_command="python",
            entry_args=[script],
            enabled=True,
        )
        resp = self.client.post(
            "/admin/api/mcp/check-all",
            json={"enabled_only": True},
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"), data)
        self.assertGreaterEqual(int(data.get("total") or 0), 1)
        items = data.get("items") or []
        row = next((x for x in items if str(x.get("server_id") or "") == "dummy-check-all"), None)
        self.assertTrue(isinstance(row, dict))
        self.assertTrue(bool((row or {}).get("ok")), row)

    def test_repair_weak_skips_healthy_and_fixes_empty_tools(self) -> None:
        script = self._write_mcp_server()
        store = SqliteStore(db_path())
        store.upsert_mcp_server(
            server_id="dummy-repair-weak",
            source_type="github",
            source_ref="https://example.com/repo.git",
            entry_command="python",
            entry_args=[script],
            enabled=True,
        )
        self.assertEqual(len(store.list_mcp_server_tools(server_id="dummy-repair-weak")), 0)

        r1 = self.client.post(
            "/admin/api/mcp/repair-weak",
            json={"enabled_only": True},
            headers=self._headers(),
        )
        self.assertEqual(r1.status_code, 200)
        d1 = r1.json()
        self.assertTrue(d1.get("ok"), d1)
        self.assertGreaterEqual(int(d1.get("selected") or 0), 1)
        items1 = d1.get("items") or []
        row1 = next((x for x in items1 if str(x.get("server_id") or "") == "dummy-repair-weak"), None)
        self.assertTrue(isinstance(row1, dict))
        self.assertTrue(bool((row1 or {}).get("ok")), row1)
        self.assertGreaterEqual(int((row1 or {}).get("tools_synced") or 0), 1)

        r2 = self.client.post(
            "/admin/api/mcp/repair-weak",
            json={"enabled_only": True},
            headers=self._headers(),
        )
        self.assertEqual(r2.status_code, 200)
        d2 = r2.json()
        self.assertTrue(d2.get("ok"), d2)
        self.assertEqual(int(d2.get("selected") or 0), 0)
        self.assertGreaterEqual(int(d2.get("skipped_healthy") or 0), 1)

    def test_repair_weak_include_disabled_server(self) -> None:
        script = self._write_mcp_server()
        store = SqliteStore(db_path())
        store.upsert_mcp_server(
            server_id="dummy-repair-disabled",
            source_type="github",
            source_ref="https://example.com/repo.git",
            entry_command="python",
            entry_args=[script],
            enabled=False,
        )
        r0 = self.client.post(
            "/admin/api/mcp/repair-weak",
            json={"enabled_only": True},
            headers=self._headers(),
        )
        self.assertEqual(r0.status_code, 200)
        self.assertEqual(int(r0.json().get("selected") or 0), 0)

        r1 = self.client.post(
            "/admin/api/mcp/repair-weak",
            json={"enabled_only": False},
            headers=self._headers(),
        )
        self.assertEqual(r1.status_code, 200)
        d1 = r1.json()
        self.assertTrue(d1.get("ok"), d1)
        self.assertGreaterEqual(int(d1.get("selected") or 0), 1)
        items = d1.get("items") or []
        row = next((x for x in items if str(x.get("server_id") or "") == "dummy-repair-disabled"), None)
        self.assertTrue(isinstance(row, dict))
        self.assertTrue(bool((row or {}).get("ok")), row)

    def test_check_updates_reports_update_candidates(self) -> None:
        store = SqliteStore(db_path())
        store.upsert_mcp_server(
            server_id="update-s1",
            source_type="npm",
            source_ref="demo-mcp",
            version="1.0.0",
            entry_command="python",
            entry_args=["-V"],
            enabled=True,
        )
        old_checker = admin_routes._check_mcp_update_row

        def _fake_checker(row: dict[str, object]) -> dict[str, object]:
            sid = str(row.get("server_id") or "")
            return {
                "server_id": sid,
                "source_type": "npm",
                "source_ref": "demo-mcp",
                "current_version": "1.0.0",
                "latest_version": "1.1.0",
                "has_update": True,
                "check_error": "",
                "check_source": "npm:dist-tags.latest",
            }

        try:
            admin_routes._check_mcp_update_row = _fake_checker  # type: ignore[assignment]
            resp = self.client.post("/admin/api/mcp/check-updates", json={"enabled_only": True}, headers=self._headers())
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data.get("ok"), data)
            self.assertGreaterEqual(int(data.get("update_count") or 0), 1)
            items = data.get("items") or []
            row = next((x for x in items if str(x.get("server_id") or "") == "update-s1"), None)
            self.assertTrue(isinstance(row, dict))
            self.assertTrue(bool((row or {}).get("has_update")), row)
        finally:
            admin_routes._check_mcp_update_row = old_checker  # type: ignore[assignment]

    def test_mcp_specialists_config(self) -> None:
        get_resp = self.client.get("/admin/api/mcp/specialists", headers=self._headers())
        self.assertEqual(get_resp.status_code, 200)
        self.assertTrue(get_resp.json().get("ok"))
        save_resp = self.client.post(
            "/admin/api/mcp/specialists",
            json={"allowed_specialists": ["generalist", "ops"]},
            headers=self._headers(),
        )
        self.assertEqual(save_resp.status_code, 200)
        data = save_resp.json()
        self.assertTrue(data.get("ok"), data)
        self.assertEqual(data.get("allowed_specialists"), ["generalist", "ops"])

    def test_mcp_binding_config_filters_invalid_servers(self) -> None:
        store = SqliteStore(db_path())
        store.upsert_mcp_server(
            server_id="bind-s1",
            source_type="github",
            source_ref="https://example.com/repo.git",
            entry_command="python",
            entry_args=["-V"],
            enabled=True,
        )
        get_resp = self.client.get("/admin/api/mcp/binding", headers=self._headers())
        self.assertEqual(get_resp.status_code, 200)
        self.assertTrue(get_resp.json().get("ok"))
        save_resp = self.client.post(
            "/admin/api/mcp/binding",
            json={"mapping": {"generalist": ["bind-s1", "missing-sid"], "ops": ["missing-sid"]}},
            headers=self._headers(),
        )
        self.assertEqual(save_resp.status_code, 200)
        data = save_resp.json()
        self.assertTrue(data.get("ok"), data)
        mapping = data.get("mapping") or {}
        self.assertEqual(mapping.get("generalist"), ["bind-s1"])
        self.assertEqual(mapping.get("ops"), [])

    def test_mcp_usage_and_delete(self) -> None:
        store = SqliteStore(db_path())
        store.upsert_mcp_server(
            server_id="usage-s1",
            source_type="github",
            source_ref="https://example.com/repo.git",
            entry_command="python",
            entry_args=["-V"],
            enabled=True,
        )
        s = store.create_session("usage session")
        sid = str(s.id)
        store.add_tool_log(
            session_id=sid,
            tool_name="mcp__usage-s1__ping",
            specialist="generalist",
            args={"x": 1},
            result={"ok": True},
        )
        usage_resp = self.client.get("/admin/api/mcp/usage?limit=50", headers=self._headers())
        self.assertEqual(usage_resp.status_code, 200)
        usage_data = usage_resp.json()
        self.assertTrue(usage_data.get("ok"), usage_data)
        summary = usage_data.get("summary") or []
        self.assertTrue(any(str(x.get("server_id") or "") == "usage-s1" for x in summary), summary)
        calls = usage_data.get("calls") or []
        self.assertTrue(any(str(x.get("specialist") or "") == "generalist" for x in calls), calls)

        del_resp = self.client.post("/admin/api/mcp/delete", json={"server_id": "usage-s1"}, headers=self._headers())
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.json().get("ok"), del_resp.json())
        left = [x for x in store.list_mcp_servers(enabled_only=False) if str(x.get("server_id") or "") == "usage-s1"]
        self.assertEqual(left, [])

    def test_mcp_uninstall_remove_record(self) -> None:
        store = SqliteStore(db_path())
        store.upsert_mcp_server(
            server_id="uninstall-s1",
            source_type="github",
            source_ref="https://example.com/repo.git",
            entry_command="python",
            entry_args=["-V"],
            enabled=True,
        )
        resp = self.client.post(
            "/admin/api/mcp/uninstall",
            json={"server_id": "uninstall-s1", "remove_record": True},
            headers=self._headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"), data)
        servers = store.list_mcp_servers(enabled_only=False)
        self.assertFalse(any(str(x.get("server_id") or "") == "uninstall-s1" for x in servers))


if __name__ == "__main__":
    unittest.main()

