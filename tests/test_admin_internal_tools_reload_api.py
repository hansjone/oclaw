from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore


class AdminInternalToolsReloadApiTests(unittest.TestCase):
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

    def test_internal_tools_reload_ok(self) -> None:
        r = self.client.post("/admin/api/tools/internal/reload", json={}, headers=self._h())
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json() or {}
        self.assertTrue(body.get("ok"))
        self.assertTrue(body.get("cleared"))


if __name__ == "__main__":
    unittest.main()

