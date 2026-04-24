"""Regression: chat_session must not change ui_session_owner implicitly on read or list."""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore


def _pw_hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


class ChatSessionIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ops.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["OPS_ASSISTANT_PASSWORD"] = "test-admin-pass"
        store = SqliteStore(str(self.db))
        t = store.create_tenant("Team")
        self.tenant_id = str(t["id"])
        store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash=_pw_hash("test-admin-pass"),
            is_active=True,
        )
        store.create_user_account(
            tenant_id=self.tenant_id,
            username="alice",
            display_name="Alice",
            role="member",
            password_hash=_pw_hash("alice-pass"),
            is_active=True,
        )
        store.create_user_account(
            tenant_id=self.tenant_id,
            username="bob",
            display_name="Bob",
            role="member",
            password_hash=_pw_hash("bob-pass"),
            is_active=True,
        )
        self.alice_id = str(store.get_user_by_username(tenant_id=self.tenant_id, username="alice")["id"])
        self.bob_id = str(store.get_user_by_username(tenant_id=self.tenant_id, username="bob")["id"])
        self.client = TestClient(create_app())
        self.client.post("/admin/api/auth/bootstrap", json={})

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _token(self, username: str, password: str) -> str:
        resp = self.client.post(
            "/admin/api/auth/login",
            json={
                "tenant_id": self.tenant_id,
                "username": username,
                "password": password,
                "purpose": "chat",
            },
        )
        data = resp.json()
        self.assertTrue(data.get("ok"), data)
        return str(data.get("token") or "")

    def test_orphan_not_visible_and_not_claimed_on_get(self) -> None:
        store = SqliteStore(str(self.db))
        orphan = store.create_session("no-owner-yet")
        self.assertIsNone(
            store.get_session_for_user(
                session_id=str(orphan.id),
                tenant_id=self.tenant_id,
                user_id=self.alice_id,
            )
        )
        tok = self._token("alice", "alice-pass")
        h = {"authorization": f"Bearer {tok}"}
        r = self.client.get(f"/admin/api/chat/sessions/{orphan.id}/messages", headers=h)
        self.assertEqual(r.status_code, 404)
        listed = self.client.get("/admin/api/chat/sessions?limit=50&offset=0", headers=h).json()
        ids = {str(s.get("id")) for s in listed.get("sessions", [])}
        self.assertNotIn(str(orphan.id), ids)

    def test_user_cannot_read_other_owned_session(self) -> None:
        store = SqliteStore(str(self.db))
        owned = store.create_session_for_user(
            title="alice-only",
            tenant_id=self.tenant_id,
            user_id=self.alice_id,
        )
        alice = self._token("alice", "alice-pass")
        bob = self._token("bob", "bob-pass")
        ra = self.client.get(
            f"/admin/api/chat/sessions/{owned.id}/messages",
            headers={"authorization": f"Bearer {alice}"},
        )
        self.assertEqual(ra.status_code, 200, ra.text)
        rb = self.client.get(
            f"/admin/api/chat/sessions/{owned.id}/messages",
            headers={"authorization": f"Bearer {bob}"},
        )
        self.assertEqual(rb.status_code, 404)

    def test_stop_requires_session_access(self) -> None:
        store = SqliteStore(str(self.db))
        owned = store.create_session_for_user(
            title="alice-only",
            tenant_id=self.tenant_id,
            user_id=self.alice_id,
        )
        bob = self._token("bob", "bob-pass")
        rs = self.client.post(
            f"/admin/api/chat/sessions/{owned.id}/stop",
            headers={"authorization": f"Bearer {bob}"},
        )
        self.assertEqual(rs.status_code, 404)


if __name__ == "__main__":
    unittest.main()
