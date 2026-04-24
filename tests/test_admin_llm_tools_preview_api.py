from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore


class AdminLLMToolsPreviewApiTests(unittest.TestCase):
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

    def test_llm_tools_preview_contains_system_time(self) -> None:
        r = self.client.get("/admin/api/tools/llm/preview?role=generalist&max_json_bytes=28000", headers=self._h())
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json() or {}
        self.assertTrue(body.get("ok"))
        wired = list(body.get("tools_wired") or [])
        names = []
        for ent in wired:
            fn = (ent or {}).get("function") if isinstance(ent, dict) else None
            nm = str((fn or {}).get("name") or "") if isinstance(fn, dict) else ""
            if nm:
                names.append(nm)
        self.assertIn("system_time", set(names))

    def test_llm_tools_preview_rejects_unknown_role(self) -> None:
        r = self.client.get("/admin/api/tools/llm/preview?role=__nope__", headers=self._h())
        self.assertEqual(r.status_code, 400, r.text)

    def test_llm_tools_preview_allows_disabling_cap(self) -> None:
        r = self.client.get("/admin/api/tools/llm/preview?role=generalist&max_json_bytes=0", headers=self._h())
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json() or {}
        self.assertTrue(body.get("ok"))
        self.assertIsNone(body.get("max_json_bytes"))


if __name__ == "__main__":
    unittest.main()

