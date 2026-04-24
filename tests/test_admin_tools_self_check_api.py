from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore


class AdminToolsSelfCheckApiTests(unittest.TestCase):
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

    def test_self_check_returns_role_summary(self) -> None:
        r = self.client.get("/admin/api/tools/self-check", headers=self._h())
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json() or {}
        self.assertTrue(body.get("ok"))
        self.assertGreaterEqual(int(body.get("roles_total") or 0), 1)
        summary = dict(body.get("summary") or {})
        self.assertIn("total_internal_tools", summary)
        self.assertIn("total_wired_tools", summary)
        self.assertIn("total_perm_ban_9999", summary)
        items = list(body.get("items") or [])
        self.assertTrue(items)
        one = dict(items[0] if items else {})
        self.assertIn("role", one)
        self.assertIn("role_mode", one)
        self.assertIn("wired_count", one)
        self.assertIn("policy_perm_ban_9999", one)


if __name__ == "__main__":
    unittest.main()

