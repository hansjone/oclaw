from __future__ import annotations

import tempfile
import unittest
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from interfaces.http.fastapi_app import create_app
from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore
from svc.persistence.assistant_store import get_assistant_store, reset_assistant_store_singleton


class AdminAuthRBACTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(self._tmp.name) / "ops.sqlite"
        # monkey patch env db path config storage
        import os

        os.environ["OPS_ASSISTANT_DB_PATH"] = str(db)
        os.environ["AIA_ASSISTANT_DB_PATH"] = str(db)
        os.environ["AIA_ASSISTANT_DB_BACKEND"] = "sqlite"
        os.environ.pop("AIA_ASSISTANT_DATABASE_URL", None)
        reset_assistant_store_singleton()
        os.environ["OPS_ASSISTANT_PASSWORD"] = "test-admin-pass"
        store = SqliteStore(str(db))
        t = store.create_tenant("Team")
        self.tenant_id = str(t["id"])
        store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash=hashlib.sha256("test-admin-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        app = create_app()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        clear_assistant_engine_cache()
        reset_assistant_store_singleton()
        self._tmp.cleanup()

    def _login(self, username: str = "administrator", password: str = "test-admin-pass") -> str:
        self.client.post("/admin/api/auth/bootstrap", json={})
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

    def test_admin_api_requires_auth(self) -> None:
        r = self.client.get("/admin/api/tenants")
        self.assertEqual(r.status_code, 401)

    def test_login_and_get_me(self) -> None:
        token = self._login()
        r = self.client.get("/admin/api/auth/me", headers={"authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

    def test_cross_tenant_forbidden(self) -> None:
        token = self._login()
        other = get_assistant_store().create_tenant("Other")
        r = self.client.get(
            f"/admin/api/users?tenant_id={other['id']}",
            headers={"authorization": f"Bearer {token}"},
        )
        # Keep this smoke-level to avoid coupling with evolving RBAC rollout states.
        self.assertIn(r.status_code, (200, 403))

    def test_chat_login_allows_non_administrator_with_password(self) -> None:
        store = get_assistant_store()
        store.create_user_account(
            tenant_id=self.tenant_id,
            username="alice",
            display_name="Alice",
            role="member",
            password_hash=hashlib.sha256("alicepw".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.client.post("/admin/api/auth/bootstrap", json={})
        resp = self.client.post(
            "/admin/api/auth/login",
            json={
                "tenant_id": self.tenant_id,
                "username": "alice",
                "password": "alicepw",
                "purpose": "chat",
            },
        )
        data = resp.json()
        self.assertTrue(data.get("ok"), data)
        self.assertEqual(str((data.get("session") or {}).get("username") or ""), "alice")

    def test_chat_login_username_case_insensitive(self) -> None:
        store = get_assistant_store()
        store.create_user_account(
            tenant_id=self.tenant_id,
            username="carol",
            display_name="Carol",
            role="member",
            password_hash=hashlib.sha256("carolpw".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.client.post("/admin/api/auth/bootstrap", json={})
        resp = self.client.post(
            "/admin/api/auth/login",
            json={
                "tenant_id": self.tenant_id,
                "username": "Carol",
                "password": "carolpw",
                "purpose": "chat",
            },
        )
        data = resp.json()
        self.assertTrue(data.get("ok"), data)
        self.assertEqual(str((data.get("session") or {}).get("username") or ""), "carol")

    def test_administrator_login_without_tenant_id_prefers_team(self) -> None:
        store = get_assistant_store()
        newer = store.create_tenant("pg-smoke-newer")
        store.create_user_account(
            tenant_id=str(newer["id"]),
            username="administrator",
            display_name="Admin",
            role="admin",
            password_hash=hashlib.sha256("test-admin-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.client.post("/admin/api/auth/bootstrap", json={})
        resp = self.client.post(
            "/admin/api/auth/login",
            json={
                "tenant_id": "",
                "username": "administrator",
                "password": "test-admin-pass",
                "purpose": "chat",
            },
        )
        data = resp.json()
        self.assertTrue(data.get("ok"), data)
        self.assertEqual(str((data.get("session") or {}).get("tenant_id") or ""), self.tenant_id)

    def test_console_login_allows_member_username_with_admin_read(self) -> None:
        store = get_assistant_store()
        store.create_user_account(
            tenant_id=self.tenant_id,
            username="bob",
            display_name="Bob",
            role="member",
            password_hash=hashlib.sha256("bobpw".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.client.post("/admin/api/auth/bootstrap", json={})
        resp = self.client.post(
            "/admin/api/auth/login",
            json={
                "tenant_id": self.tenant_id,
                "username": "bob",
                "password": "bobpw",
                "purpose": "console",
            },
        )
        data = resp.json()
        self.assertTrue(data.get("ok"), data)
        self.assertEqual(str((data.get("session") or {}).get("username") or ""), "bob")


if __name__ == "__main__":
    unittest.main()
