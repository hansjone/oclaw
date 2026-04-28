from __future__ import annotations

import base64
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore

MINI_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class ChatProfileApiTests(unittest.TestCase):
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
            password_hash=hashlib.sha256("test-admin-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.client = TestClient(create_app())
        self.client.post("/admin/api/auth/bootstrap", json={})
        resp = self.client.post(
            "/admin/api/auth/login",
            json={
                "tenant_id": self.tenant_id,
                "username": "administrator",
                "password": "test-admin-pass",
                "purpose": "console",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.token = str(resp.json().get("token") or "")
        store.create_user_account(
            tenant_id=self.tenant_id,
            username="alice",
            display_name="Alice",
            role="member",
            password_hash=hashlib.sha256("alice-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        resp_alice = self.client.post(
            "/admin/api/auth/login",
            json={
                "tenant_id": self.tenant_id,
                "username": "alice",
                "password": "alice-pass",
                "purpose": "console",
            },
        )
        self.assertEqual(resp_alice.status_code, 200, resp_alice.text)
        self.alice_token = str(resp_alice.json().get("token") or "")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _h(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}"}

    def _h_alice(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.alice_token}"}

    def test_profile_get_patch_avatar_delete(self) -> None:
        g = self.client.get("/admin/api/chat/profile", headers=self._h())
        self.assertEqual(g.status_code, 200, g.text)
        data = g.json()
        self.assertTrue(data.get("ok"))
        prof = data.get("profile") or {}
        self.assertEqual(prof.get("username"), "administrator")
        self.assertFalse(prof.get("avatar_attachment_id"))

        p = self.client.patch(
            "/admin/api/chat/profile",
            json={"display_name": "Admin Renamed"},
            headers=self._h(),
        )
        self.assertEqual(p.status_code, 200, p.text)
        self.assertEqual((p.json().get("profile") or {}).get("display_name"), "Admin Renamed")

        up = self.client.post(
            "/admin/api/chat/profile/avatar",
            files={"file": ("x.png", MINI_PNG, "image/png")},
            headers=self._h(),
        )
        self.assertEqual(up.status_code, 200, up.text)
        aid = str((up.json() or {}).get("avatar_attachment_id") or "").strip()
        self.assertTrue(aid)

        g2 = self.client.get("/admin/api/chat/profile", headers=self._h())
        self.assertEqual((g2.json().get("profile") or {}).get("avatar_attachment_id"), aid)

        att = self.client.get(f"/admin/api/chat/attachments/{aid}", headers=self._h())
        self.assertEqual(att.status_code, 200)
        self.assertTrue(len(att.content) > 10)

        d = self.client.delete("/admin/api/chat/profile/avatar", headers=self._h())
        self.assertEqual(d.status_code, 200, d.text)
        g3 = self.client.get("/admin/api/chat/profile", headers=self._h())
        self.assertFalse((g3.json().get("profile") or {}).get("avatar_attachment_id"))

    def test_attachment_endpoint_rejects_invalid_attachment_id(self) -> None:
        r = self.client.get("/admin/api/chat/attachments/not-a-valid-id", headers=self._h())
        self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual((r.json() or {}).get("detail"), "attachment_id_invalid")

    def test_attachment_endpoint_forbids_unowned_attachment(self) -> None:
        up = self.client.post(
            "/admin/api/chat/profile/avatar",
            files={"file": ("x.png", MINI_PNG, "image/png")},
            headers=self._h(),
        )
        self.assertEqual(up.status_code, 200, up.text)
        aid = str((up.json() or {}).get("avatar_attachment_id") or "").strip()
        self.assertTrue(aid)

        me = self.client.get(f"/admin/api/chat/attachments/{aid}", headers=self._h())
        self.assertEqual(me.status_code, 200, me.text)

        other = self.client.get(f"/admin/api/chat/attachments/{aid}", headers=self._h_alice())
        self.assertEqual(other.status_code, 403, other.text)
        self.assertEqual((other.json() or {}).get("detail"), "attachment_forbidden")

    def test_attachment_acl_strict_requires_backfill_or_acl(self) -> None:
        prev = os.environ.get("AIA_ATTACHMENT_ACL_STRICT")
        os.environ["AIA_ATTACHMENT_ACL_STRICT"] = "1"
        try:
            # Upload an avatar (this is not linked into ACL; access is via avatar_attachment_id).
            up = self.client.post(
                "/admin/api/chat/profile/avatar",
                files={"file": ("x.png", MINI_PNG, "image/png")},
                headers=self._h(),
            )
            self.assertEqual(up.status_code, 200, up.text)
            aid = str((up.json() or {}).get("avatar_attachment_id") or "").strip()
            self.assertTrue(aid)
            # Avatar download remains allowed under strict mode.
            att = self.client.get(f"/admin/api/chat/attachments/{aid}", headers=self._h())
            self.assertEqual(att.status_code, 200, att.text)
        finally:
            if prev is None:
                os.environ.pop("AIA_ATTACHMENT_ACL_STRICT", None)
            else:
                os.environ["AIA_ATTACHMENT_ACL_STRICT"] = prev


if __name__ == "__main__":
    unittest.main()
