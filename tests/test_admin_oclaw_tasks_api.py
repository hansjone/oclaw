from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore


class AdminOclawTasksApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ops.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["OPS_ASSISTANT_PASSWORD"] = "test-admin-pass"
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
        self.session_a = self.store.create_session_for_user(
            title="A",
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        ).id
        self.task_a = self.store.oclaw_task_create(
            tenant_id=self.tenant_id,
            session_id=self.session_a,
            payload={"text": "hello"},
        )

        t2 = self.store.create_tenant("TeamB")
        other_tenant = str(t2["id"])
        other_user = self.store.create_user_account(
            tenant_id=other_tenant,
            username="boss",
            display_name="Boss",
            role="owner",
            password_hash=hashlib.sha256("bosspw".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        other_session = self.store.create_session_for_user(
            title="B",
            tenant_id=other_tenant,
            user_id=str(other_user["id"]),
        ).id
        self.store.oclaw_task_create(tenant_id=other_tenant, session_id=other_session, payload={"text": "secret"})

        self.client = TestClient(create_app())
        self.client.post("/admin/api/auth/bootstrap", json={})

    def tearDown(self) -> None:
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

    def test_oclaw_tasks_api_lists_only_current_tenant(self) -> None:
        token = self._login()
        headers = {"authorization": f"Bearer {token}"}
        r = self.client.get("/admin/api/oclaw/tasks?limit=50", headers=headers)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body.get("ok"))
        tasks = body.get("tasks") or []
        self.assertTrue(tasks)
        self.assertTrue(all(str(x.get("tenant_id") or "") == self.tenant_id for x in tasks))
        self.assertTrue(any(str(x.get("id") or "") == self.task_a.id for x in tasks))

    def test_oclaw_task_get_by_id(self) -> None:
        token = self._login()
        headers = {"authorization": f"Bearer {token}"}
        r = self.client.get(f"/admin/api/oclaw/tasks?task_id={self.task_a.id}", headers=headers)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body.get("ok"))
        task = body.get("task") or {}
        self.assertEqual(str(task.get("id") or ""), self.task_a.id)


if __name__ == "__main__":
    unittest.main()

