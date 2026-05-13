from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from interfaces.http.fastapi_app import create_app
from svc.config.paths import db_path
from svc.persistence.sqlite_store import SqliteStore


class AdminAuditPaginationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(self._tmp.name) / "ops.sqlite"
        import os

        os.environ["OPS_ASSISTANT_DB_PATH"] = str(db)
        os.environ["OPS_ASSISTANT_PASSWORD"] = "audit-test-pass"
        store = SqliteStore(str(db))
        tenant = store.create_tenant("Team")
        self.tenant_id = str(tenant["id"])
        store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash=hashlib.sha256("audit-test-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        store.create_user_account(
            tenant_id=self.tenant_id,
            username="operator",
            display_name="Operator",
            role="member",
            password_hash=hashlib.sha256("operator-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.store = store
        app = create_app()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _login(self, username: str = "administrator", password: str = "audit-test-pass") -> str:
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

    def _seed_logs(self) -> None:
        # Insert logs in order; endpoint sorts DESC by id.
        rows = [
            ("administrator", "user.create", "ok"),
            ("operator", "user.create", "ok"),
            ("administrator", "user.disable", "ok"),
            ("administrator", "user.delete", "failed"),
            ("operator", "user.delete", "ok"),
            ("administrator", "user.disable", "failed"),
        ]
        for actor, action, status in rows:
            self.store.add_admin_audit_log(
                actor_tenant_id=self.tenant_id,
                actor_user_id=actor,
                action=action,
                target_type="user",
                target_id="u-1",
                status=status,
                detail={"k": f"{actor}:{action}:{status}"},
            )

    def test_admin_audit_pagination_returns_total_and_offset_slice(self) -> None:
        self._seed_logs()
        token = self._login()
        resp = self.client.get(
            "/admin/api/admin-audit?limit=2&offset=2",
            headers={"authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data.get("ok"), data)
        self.assertEqual(int(data.get("limit") or 0), 2)
        self.assertEqual(int(data.get("offset") or 0), 2)
        self.assertEqual(int(data.get("total") or 0), 6)
        items = data.get("items") or []
        self.assertEqual(len(items), 2)
        # Desc by id => offset 2 starts from the 3rd newest.
        self.assertEqual(str(items[0].get("action") or ""), "user.delete")
        self.assertEqual(str(items[0].get("status") or ""), "failed")
        self.assertEqual(str(items[1].get("action") or ""), "user.disable")
        self.assertEqual(str(items[1].get("status") or ""), "ok")
        # Legacy compatibility field kept.
        self.assertEqual(len(data.get("logs") or []), len(items))

    def test_admin_audit_filtering_applies_to_total_and_items(self) -> None:
        self._seed_logs()
        token = self._login()
        resp = self.client.get(
            "/admin/api/admin-audit?limit=5&offset=0&action=user.disable&status=failed",
            headers={"authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        items = data.get("items") or []
        self.assertEqual(int(data.get("total") or 0), 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(str(items[0].get("action") or ""), "user.disable")
        self.assertEqual(str(items[0].get("status") or ""), "failed")


if __name__ == "__main__":
    unittest.main()

