from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from interfaces.http.fastapi_app import create_app
from svc.persistence.sqlite_store import SqliteStore


class AdminMcpToolWireRoleModeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ops.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["OPS_ASSISTANT_PASSWORD"] = "test-admin-pass"
        self.store = SqliteStore(str(self.db))
        t = self.store.create_tenant("Team")
        self.tenant_id = str(t["id"])
        self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash=hashlib.sha256("test-admin-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.client = TestClient(create_app())
        self.client.post("/admin/api/auth/bootstrap", json={})
        r = self.client.post(
            "/admin/api/auth/login",
            json={"tenant_id": self.tenant_id, "username": "administrator", "password": "test-admin-pass", "purpose": "console"},
        )
        self.token = str((r.json() or {}).get("token") or "")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _h(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}"}

    def test_role_mode_save_and_snapshot(self) -> None:
        s = self.client.post(
            "/admin/api/mcp/tool-wire/role-mode",
            json={"role": "ops", "mode": "forbidden"},
            headers=self._h(),
        )
        self.assertEqual(s.status_code, 200, s.text)
        body = s.json() or {}
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("role"), "ops")
        self.assertEqual(body.get("mode"), "forbidden")

        g = self.client.get("/admin/api/mcp/tool-wire?role=ops", headers=self._h())
        self.assertEqual(g.status_code, 200, g.text)
        gb = g.json() or {}
        self.assertTrue(gb.get("ok"))
        self.assertEqual(gb.get("role"), "ops")
        self.assertEqual(gb.get("role_mode"), "forbidden")

    def test_role_mode_rejects_unknown_role(self) -> None:
        s = self.client.post(
            "/admin/api/mcp/tool-wire/role-mode",
            json={"role": "unknown_role_x", "mode": "restricted"},
            headers=self._h(),
        )
        self.assertEqual(s.status_code, 400, s.text)
        self.assertIn("invalid_role", s.text)

    def test_policies_batch_supports_role_scope(self) -> None:
        r = self.client.post(
            "/admin/api/mcp/tool-wire/policies/batch",
            json={"role": "ops", "level": 9999, "wire_names": ["mcp__echo__ping"]},
            headers=self._h(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json() or {}
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("role"), "ops")
        raw = str(self.store.get_setting("mcp_tool_wire_tool_policies_by_role") or "").strip() or "{}"
        obj = json.loads(raw)
        self.assertEqual(int(((obj.get("ops") or {}).get("mcp__echo__ping") or 0)), 9999)

    def test_e2e_role_mode_then_batch_then_refresh_consistent(self) -> None:
        # 1) switch role mode for ops
        s = self.client.post(
            "/admin/api/mcp/tool-wire/role-mode",
            json={"role": "ops", "mode": "restricted"},
            headers=self._h(),
        )
        self.assertEqual(s.status_code, 200, s.text)
        self.assertTrue((s.json() or {}).get("ok"))

        # 2) apply role-scoped batch policy for ops
        b = self.client.post(
            "/admin/api/mcp/tool-wire/policies/batch",
            json={"role": "ops", "level": 0, "wire_names": ["mcp__echo__ping"]},
            headers=self._h(),
        )
        self.assertEqual(b.status_code, 200, b.text)
        bb = b.json() or {}
        self.assertTrue(bb.get("ok"))
        self.assertEqual(bb.get("role"), "ops")

        # 3) query snapshot for ops (equivalent to refresh + reload)
        g1 = self.client.get("/admin/api/mcp/tool-wire?role=ops", headers=self._h())
        self.assertEqual(g1.status_code, 200, g1.text)
        body1 = g1.json() or {}
        self.assertTrue(body1.get("ok"))
        self.assertEqual(body1.get("role"), "ops")
        self.assertEqual(body1.get("role_mode"), "restricted")
        self.assertEqual(int((body1.get("policies") or {}).get("mcp__echo__ping") or 0), 0)

        # 4) switch another role and ensure isolation
        s2 = self.client.post(
            "/admin/api/mcp/tool-wire/role-mode",
            json={"role": "generalist", "mode": "forbidden"},
            headers=self._h(),
        )
        self.assertEqual(s2.status_code, 200, s2.text)

        g2 = self.client.get("/admin/api/mcp/tool-wire?role=generalist", headers=self._h())
        self.assertEqual(g2.status_code, 200, g2.text)
        body2 = g2.json() or {}
        self.assertEqual(body2.get("role_mode"), "forbidden")
        # no accidental carry-over from ops role policies
        self.assertNotIn("mcp__echo__ping", dict(body2.get("policies") or {}))


if __name__ == "__main__":
    unittest.main()

