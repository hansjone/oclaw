from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore


class AdminSessionMonitorApiTests(unittest.TestCase):
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
        self.admin_user_id = str(admin["id"])
        alice = self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="alice",
            display_name="Alice",
            role="member",
            password_hash=hashlib.sha256("alicepw".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.alice_user_id = str(alice["id"])

        # Same-tenant sessions for alice: one active, one inactive (older than 30m)
        self.alice_active_session = self.store.create_session_for_user(
            title="Alice active",
            tenant_id=self.tenant_id,
            user_id=self.alice_user_id,
        )
        self.store.add_message(
            session_id=self.alice_active_session.id,
            role="user",
            content="hello",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.store.add_trace_event(
            session_id=self.alice_active_session.id,
            trace_id="t1",
            span_id="s1",
            parent_span_id=None,
            event_type="llm_result",
            payload={"response_tokens_est": 123, "prompt_tokens_est": 45},
        )
        inactive_ts = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
        self.alice_inactive_session = self.store.create_session_for_user(
            title="Alice inactive",
            tenant_id=self.tenant_id,
            user_id=self.alice_user_id,
        )
        self.store.add_message(
            session_id=self.alice_inactive_session.id,
            role="user",
            content="old",
            timestamp=inactive_ts,
        )

        # Different tenant data should not leak.
        other = self.store.create_tenant("Other")
        self.other_tenant_id = str(other["id"])
        bob = self.store.create_user_account(
            tenant_id=self.other_tenant_id,
            username="bob",
            display_name="Bob",
            role="owner",
            password_hash=hashlib.sha256("bobpw".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        bob_session = self.store.create_session_for_user(
            title="Bob private",
            tenant_id=self.other_tenant_id,
            user_id=str(bob["id"]),
        )
        self.store.add_message(
            session_id=bob_session.id,
            role="user",
            content="secret",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        self.client = TestClient(create_app())
        self.client.post("/admin/api/auth/bootstrap", json={})

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _login(self, username: str, password: str) -> str:
        resp = self.client.post(
            "/admin/api/auth/login",
            json={
                "tenant_id": self.tenant_id,
                "username": username,
                "password": password,
                "purpose": "console",
            },
        )
        data = resp.json()
        self.assertTrue(data.get("ok"), data)
        return str(data.get("token") or "")

    def test_administrator_can_view_cross_user_stats_and_sessions(self) -> None:
        token = self._login("administrator", "test-admin-pass")
        headers = {"authorization": f"Bearer {token}"}

        stats = self.client.get("/admin/api/chat/admin/user-stats?limit=200", headers=headers)
        self.assertEqual(stats.status_code, 200)
        body = stats.json()
        self.assertTrue(body.get("ok"))
        users = body.get("users") or []
        self.assertTrue(any(str(u.get("username") or "") == "alice" for u in users))
        self.assertFalse(any(str(u.get("username") or "") == "bob" for u in users))
        totals = body.get("totals") or {}
        self.assertGreaterEqual(int(totals.get("total_tokens_est") or 0), 168)

        sess = self.client.get(
            f"/admin/api/chat/admin/sessions?user_id={self.alice_user_id}&active_only=1&limit=200",
            headers=headers,
        )
        self.assertEqual(sess.status_code, 200)
        sbody = sess.json()
        self.assertTrue(sbody.get("ok"))
        rows = sbody.get("sessions") or []
        self.assertTrue(rows)
        self.assertTrue(all(str(r.get("user_id") or "") == self.alice_user_id for r in rows))
        self.assertTrue(all(bool(r.get("is_active_30m")) for r in rows))
        self.assertEqual(len(rows), 1)

    def test_non_administrator_forbidden(self) -> None:
        token = self._login("alice", "alicepw")
        headers = {"authorization": f"Bearer {token}"}
        r1 = self.client.get("/admin/api/chat/admin/user-stats", headers=headers)
        r2 = self.client.get("/admin/api/chat/admin/sessions", headers=headers)
        self.assertEqual(r1.status_code, 403)
        self.assertEqual(r2.status_code, 403)


if __name__ == "__main__":
    unittest.main()
