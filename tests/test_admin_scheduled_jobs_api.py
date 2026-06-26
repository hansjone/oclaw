from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from interfaces.http.fastapi_app import create_app
from svc.persistence.assistant_store import reset_assistant_store_singleton
from svc.persistence.sqlite_store import SqliteStore


class AdminScheduledJobsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "sched_admin.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["OPS_ASSISTANT_PASSWORD"] = "test-admin-pass"
        os.environ["AIA_ASSISTANT_DB_BACKEND"] = "sqlite"
        reset_assistant_store_singleton()
        self.store = SqliteStore(str(self.db))
        t1 = self.store.create_tenant("TeamA")
        self.tenant_id = str(t1["id"])
        admin = self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash=hashlib.sha256("test-admin-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.user_id = str(admin["id"])
        self.client = TestClient(create_app())
        self.client.post("/admin/api/auth/bootstrap", json={})

    def tearDown(self) -> None:
        reset_assistant_store_singleton()
        self._tmp.cleanup()

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

    def test_scheduled_jobs_crud(self) -> None:
        token = self._login()
        headers = {"authorization": f"Bearer {token}"}
        once_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        create = self.client.post(
            "/admin/api/scheduled-jobs",
            headers=headers,
            json={
                "name": "Test job",
                "prompt_text": "Say hello",
                "schedule_kind": "once",
                "schedule_expr": once_at,
                "specialist": "generalist",
            },
        )
        self.assertEqual(create.status_code, 200, create.text)
        body = create.json()
        self.assertTrue(body.get("ok"), body)
        job_id = str((body.get("job") or {}).get("id") or "")
        self.assertTrue(job_id)

        listed = self.client.get("/admin/api/scheduled-jobs", headers=headers)
        self.assertTrue(listed.json().get("ok"))
        self.assertGreaterEqual(len(listed.json().get("items") or []), 1)

        pause = self.client.post(f"/admin/api/scheduled-jobs/{job_id}/pause", headers=headers, json={})
        self.assertTrue(pause.json().get("ok"))

        resume = self.client.post(f"/admin/api/scheduled-jobs/{job_id}/resume", headers=headers, json={})
        self.assertTrue(resume.json().get("ok"))

        runs = self.client.get(f"/admin/api/scheduled-jobs/{job_id}/runs", headers=headers)
        self.assertTrue(runs.json().get("ok"))

        patch = self.client.patch(
            f"/admin/api/scheduled-jobs/{job_id}",
            headers=headers,
            json={
                "name": "Updated job",
                "schedule_kind": "interval",
                "schedule_expr": "7200",
                "prompt_text": "Stand up hourly",
                "specialist": "generalist",
            },
        )
        self.assertEqual(patch.status_code, 200, patch.text)
        patched = patch.json()
        self.assertTrue(patched.get("ok"), patched)
        job = patched.get("job") or {}
        self.assertEqual(str(job.get("name") or ""), "Updated job")
        self.assertEqual(str(job.get("schedule_kind") or ""), "interval")
        self.assertEqual(str(job.get("schedule_expr") or ""), "7200")
        self.assertEqual(str(job.get("prompt_text") or ""), "Stand up hourly")


if __name__ == "__main__":
    unittest.main()
