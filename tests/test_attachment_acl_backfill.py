from __future__ import annotations

import base64
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.files.attachment_assets import AttachmentAssetStore
from oclaw.platform.persistence.sqlite_store import SqliteStore


def _pw_hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


class AttachmentAclBackfillTests(unittest.TestCase):
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
        self.alice_id = str(store.get_user_by_username(tenant_id=self.tenant_id, username="alice")["id"])
        self.client = TestClient(create_app())
        self.client.post("/admin/api/auth/bootstrap", json={})
        tok = self.client.post(
            "/admin/api/auth/login",
            json={"tenant_id": self.tenant_id, "username": "alice", "password": "alice-pass", "purpose": "chat"},
        ).json()
        self.token = str(tok.get("token") or "")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _h(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}"}

    def test_add_message_links_acl_for_strict_download(self) -> None:
        store = SqliteStore(str(self.db))
        sess = store.create_session_for_user(title="t", tenant_id=self.tenant_id, user_id=self.alice_id)
        ast = AttachmentAssetStore()
        blob = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
        meta = ast.save_bytes(blob, filename="x.png", mime="image/png")
        aid = str(meta.attachment_id or "").strip()
        store.add_message(
            session_id=str(sess.id),
            role="assistant",
            content="here",
            attachments=[{"type": "image_ref", "attachment_id": aid, "mime": "image/png", "name": "x.png"}],
        )

        prev = os.environ.get("AIA_ATTACHMENT_ACL_STRICT")
        os.environ["AIA_ATTACHMENT_ACL_STRICT"] = "1"
        try:
            # Strict mode: add_message should have written attachment_acl (not only tool_result rows).
            r0 = self.client.get(f"/admin/api/chat/attachments/{aid}", headers=self._h())
            self.assertEqual(r0.status_code, 200, r0.text)
            self.assertTrue(len(r0.content) > 10)

            # Backfill remains idempotent.
            res = store.backfill_attachment_acl_from_messages(tenant_id=self.tenant_id, limit_messages=5000)
            self.assertTrue(res.get("ok"), res)
            r1 = self.client.get(f"/admin/api/chat/attachments/{aid}", headers=self._h())
            self.assertEqual(r1.status_code, 200, r1.text)
            self.assertTrue(len(r1.content) > 10)
        finally:
            if prev is None:
                os.environ.pop("AIA_ATTACHMENT_ACL_STRICT", None)
            else:
                os.environ["AIA_ATTACHMENT_ACL_STRICT"] = prev


if __name__ == "__main__":
    unittest.main()

