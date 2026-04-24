from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore


class AdminChatWikiEventsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ops.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["OPS_ASSISTANT_PASSWORD"] = "test-admin-pass"
        self.store = SqliteStore(str(self.db))
        tenant = self.store.create_tenant("Team")
        self.tenant_id = str(tenant["id"])
        user = self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash=hashlib.sha256("test-admin-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.user_id = str(user["id"])
        self.session_id = self.store.create_session_for_user(title="chat", tenant_id=self.tenant_id, user_id=self.user_id).id
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
                "purpose": "chat",
            },
        )
        body = resp.json()
        self.assertTrue(body.get("ok"), body)
        return str(body.get("token") or "")

    def _login_user(self, username: str) -> str:
        resp = self.client.post(
            "/admin/api/auth/login",
            json={
                "tenant_id": self.tenant_id,
                "username": username,
                "password": "test-admin-pass",
                "purpose": "chat",
            },
        )
        body = resp.json()
        self.assertTrue(body.get("ok"), body)
        return str(body.get("token") or "")

    def test_wiki_events_endpoint_returns_finished_wiki_capture_tasks(self) -> None:
        token = self._login()
        task = self.store.openclaw_task_create(
            tenant_id=self.tenant_id,
            session_id=str(self.session_id),
            task_type="wiki_capture",
            payload={"kind": "captureAfterTurn", "session_id": str(self.session_id)},
        )
        self.assertTrue(self.store.openclaw_task_finish(task_id=task.id, result={"ok": True, "dedupMerge": {"merged_count": 1, "skipped_dup": 0}}))
        headers = {"authorization": f"Bearer {token}", "accept": "application/json"}
        resp = self.client.get(
            f"/admin/api/chat/sessions/{self.session_id}/wiki-events?limit=10",
            headers=headers,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("ok"), body)
        events = body.get("events") or []
        self.assertTrue(isinstance(events, list) and len(events) >= 1, body)
        last = events[-1]
        self.assertEqual(str(last.get("task_id") or ""), str(task.id))
        self.assertEqual(str(last.get("status") or ""), "done")
        self.assertTrue(bool(last.get("ok")))
        result = last.get("result") or {}
        self.assertEqual(int(((result.get("dedupMerge") or {}).get("merged_count")) or 0), 1)

    def test_wiki_events_endpoint_requires_administrator(self) -> None:
        user = self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="alice",
            display_name="Alice",
            role="member",
            password_hash=hashlib.sha256("test-admin-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        _ = user
        token = self._login_user("alice")
        headers = {"authorization": f"Bearer {token}", "accept": "application/json"}
        resp = self.client.get(
            f"/admin/api/chat/sessions/{self.session_id}/wiki-events?limit=10",
            headers=headers,
        )
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self.assertEqual(str(body.get("detail") or ""), "administrator_only")


if __name__ == "__main__":
    unittest.main()

