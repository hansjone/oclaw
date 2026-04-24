from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore


class AdminOpenClawRunsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ops.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["OPS_ASSISTANT_PASSWORD"] = "test-admin-pass"
        self.store = SqliteStore(str(self.db))
        t = self.store.create_tenant("Team")
        self.tenant_id = str(t["id"])
        admin = self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash=hashlib.sha256("test-admin-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.user_id = str(admin["id"])
        self.session_id = self.store.create_session_for_user(
            title="s",
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        ).id
        self.store.openclaw_run_upsert(
            run_id="run-1",
            tenant_id=self.tenant_id,
            session_id=self.session_id,
            status="failed",
            payload={"stop_reason": "non_retryable_error"},
        )
        self.store.openclaw_attempt_append(
            run_id="run-1",
            tenant_id=self.tenant_id,
            session_id=self.session_id,
            attempt_no=1,
            status="failed",
            reason="bad_request_invalid_input",
            payload={"error_code": "attempt_error"},
        )
        self.client = TestClient(create_app())
        self.client.post("/admin/api/auth/bootstrap", json={})

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _login(self) -> str:
        r = self.client.post(
            "/admin/api/auth/login",
            json={"tenant_id": self.tenant_id, "username": "administrator", "password": "test-admin-pass", "purpose": "console"},
        )
        body = r.json()
        self.assertTrue(body.get("ok"), body)
        return str(body.get("token") or "")

    def test_runs_list_and_get(self) -> None:
        token = self._login()
        headers = {"authorization": f"Bearer {token}"}
        r1 = self.client.get(f"/admin/api/openclaw/runs?session_id={self.session_id}&include_attempts=1", headers=headers)
        self.assertEqual(r1.status_code, 200)
        b1 = r1.json()
        self.assertTrue(b1.get("ok"))
        self.assertTrue(isinstance((b1.get("retry_policy") or {}).get("effective_retryable_error_codes"), list))
        rows = b1.get("runs") or []
        self.assertTrue(rows)
        self.assertEqual(str(rows[0].get("run_id") or ""), "run-1")
        self.assertTrue(isinstance(rows[0].get("attempts"), list))

        r2 = self.client.get("/admin/api/openclaw/runs?run_id=run-1&include_attempts=1", headers=headers)
        self.assertEqual(r2.status_code, 200)
        b2 = r2.json()
        self.assertTrue(b2.get("ok"))
        run = b2.get("run") or {}
        self.assertEqual(str(run.get("run_id") or ""), "run-1")
        self.assertTrue(isinstance(run.get("attempts"), list))


if __name__ == "__main__":
    unittest.main()

