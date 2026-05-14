"""端到端：管理台登录 → 创建聊天会话 → 发送一条消息（不依赖外网 LLM）。"""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from interfaces.http.fastapi_app import create_app
from svc.persistence.sqlite_store import SqliteStore


class ChatSessionFullSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ops.sqlite"
        # 本机若已 export PG 助手库，get_assistant_store 会连 PG，与本测试临时 SQLite 种子不一致 → login 失败。
        for k in (
            "AIA_ASSISTANT_DB_BACKEND",
            "OPS_ASSISTANT_DB_BACKEND",
            "AIA_ASSISTANT_DATABASE_URL",
            "OPS_ASSISTANT_DATABASE_URL",
            "AIA_ASSISTANT_PG_DSN",
            "OPS_ASSISTANT_PG_DSN",
        ):
            os.environ.pop(k, None)
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["OPS_ASSISTANT_PASSWORD"] = "test-admin-pass"
        os.environ["OPS_ASSISTANT_MODE"] = "rule"
        from svc.persistence.assistant_store import reset_assistant_store_singleton
        from svc.persistence.db.engine import clear_assistant_engine_cache

        clear_assistant_engine_cache()
        reset_assistant_store_singleton()
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
        self.token = self._login()

    def tearDown(self) -> None:
        for k in ("OPS_ASSISTANT_DB_PATH", "OPS_ASSISTANT_MODE"):
            os.environ.pop(k, None)
        self._tmp.cleanup()

    def _headers(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}"}

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

    def test_create_session_send_message_list_messages(self) -> None:
        cr = self.client.post("/admin/api/chat/sessions", json={"title": "smoke"}, headers=self._headers())
        self.assertEqual(cr.status_code, 200, cr.text)
        cj = cr.json()
        self.assertTrue(cj.get("ok"), cj)
        sid = str((cj.get("session") or {}).get("id") or "")
        self.assertTrue(sid, cj)

        mr = self.client.post(
            f"/admin/api/chat/sessions/{sid}/messages",
            json={"text": "ping"},
            headers=self._headers(),
        )
        self.assertEqual(mr.status_code, 200, mr.text)
        mj = mr.json()
        self.assertTrue(mj.get("ok"), mj)
        reply = str(mj.get("reply") or "")
        self.assertTrue(len(reply) > 0, mj)

        lr = self.client.get(f"/admin/api/chat/sessions/{sid}/messages", headers=self._headers())
        self.assertEqual(lr.status_code, 200, lr.text)
        lj = lr.json()
        self.assertTrue(lj.get("ok"), lj)
        msgs = lj.get("messages") or []
        roles = [str(m.get("role") or "") for m in msgs if isinstance(m, dict)]
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)


if __name__ == "__main__":
    unittest.main()
