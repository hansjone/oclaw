from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from interfaces.http.fastapi_app import create_app
from svc.persistence.sqlite_store import SqliteStore


class AdminToolsExposureTraceSettingApiTests(unittest.TestCase):
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

    def test_exposure_trace_setting_get_and_save(self) -> None:
        g1 = self.client.get("/admin/api/tools/exposure-trace-setting", headers=self._h())
        self.assertEqual(g1.status_code, 200, g1.text)
        self.assertTrue((g1.json() or {}).get("ok"))

        s = self.client.post("/admin/api/tools/exposure-trace-setting", json={"enabled": True}, headers=self._h())
        self.assertEqual(s.status_code, 200, s.text)
        self.assertTrue((s.json() or {}).get("enabled"))

        g2 = self.client.get("/admin/api/tools/exposure-trace-setting", headers=self._h())
        self.assertEqual(g2.status_code, 200, g2.text)
        self.assertTrue((g2.json() or {}).get("enabled"))


if __name__ == "__main__":
    unittest.main()

