from __future__ import annotations

import json
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore


class AdminChatStreamAsyncTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ops.sqlite"
        self.oclaw_cfg = Path(self._tmp.name) / "oclaw.json"
        self.oclaw_cfg.write_text(
            json.dumps(
                {
                    "plugins": {
                        "entries": {
                            "memory-wiki": {
                                "auto": {
                                    "attachments": {
                                        "tabular": {
                                            "max_rows_read": 5000,
                                            "max_columns": 200,
                                            "max_cell_chars": 500,
                                            "max_excel_sheets": 50,
                                            "sql_timeout_ms": 8000,
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["OPS_ASSISTANT_PASSWORD"] = "test-admin-pass"
        os.environ["AIA_OCLAW_CONFIG_PATH"] = str(self.oclaw_cfg)
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
        os.environ.pop("AIA_OCLAW_CONFIG_PATH", None)
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

    def test_stream_done_contains_async_task_id(self) -> None:
        token = self._login()
        headers = {
            "authorization": f"Bearer {token}",
            "accept": "text/event-stream",
            "content-type": "application/json",
        }
        with self.client.stream(
            "POST",
            f"/admin/api/chat/sessions/{self.session_id}/messages/stream",
            headers=headers,
            json={"text": "请总结并发送到项目群"},
        ) as resp:
            self.assertEqual(resp.status_code, 200)
            done = None
            for line in resp.iter_lines():
                if not line:
                    continue
                s = line.decode("utf-8") if isinstance(line, bytes) else str(line)
                if not s.startswith("data:"):
                    continue
                ev = json.loads(s[5:].strip())
                if ev.get("type") == "done":
                    done = ev
                    break
        self.assertIsNotNone(done)
        self.assertEqual(str(done.get("mode") or ""), "async_task")
        self.assertTrue(str(done.get("task_id") or "").strip())

    def test_non_stream_send_contains_async_task_id(self) -> None:
        token = self._login()
        headers = {
            "authorization": f"Bearer {token}",
            "accept": "application/json",
            "content-type": "application/json",
        }
        resp = self.client.post(
            f"/admin/api/chat/sessions/{self.session_id}/messages",
            headers=headers,
            json={"text": "请总结并发送到项目群"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("ok"), body)
        self.assertEqual(str(body.get("mode") or ""), "async_task")
        self.assertTrue(str(body.get("task_id") or "").strip())

    def test_async_task_payload_contains_selected_specialist(self) -> None:
        token = self._login()
        headers = {
            "authorization": f"Bearer {token}",
            "accept": "application/json",
            "content-type": "application/json",
        }
        resp = self.client.post(
            f"/admin/api/chat/sessions/{self.session_id}/messages",
            headers=headers,
            json={"text": "请总结并发送到项目群", "chat_mode": "specialist", "specialist": "generalist"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("ok"), body)
        self.assertEqual(str(body.get("mode") or ""), "async_task")
        task_id = str(body.get("task_id") or "")
        self.assertTrue(task_id.strip())
        task = self.store.openclaw_task_get(task_id=task_id, tenant_id=self.tenant_id)
        self.assertIsNotNone(task)
        payload = json.loads(str(task.payload or "{}"))
        self.assertEqual(str(payload.get("selected_specialist") or ""), "generalist")

    def test_session_mode_setting_roundtrip(self) -> None:
        token = self._login()
        headers = {
            "authorization": f"Bearer {token}",
            "accept": "application/json",
            "content-type": "application/json",
        }
        resp1 = self.client.post(
            f"/admin/api/chat/sessions/{self.session_id}/mode",
            headers=headers,
            json={"interaction_mode": "expert", "specialist": "ops", "memory_mode": "store_only"},
        )
        self.assertEqual(resp1.status_code, 200)
        body1 = resp1.json()
        self.assertTrue(body1.get("ok"), body1)
        self.assertEqual(str(body1.get("interaction_mode") or ""), "expert")
        self.assertEqual(str(body1.get("specialist") or ""), "ops")
        self.assertEqual(str(body1.get("memory_mode") or ""), "store_only")

        resp2 = self.client.get(
            f"/admin/api/chat/sessions/{self.session_id}/mode",
            headers={"authorization": f"Bearer {token}", "accept": "application/json"},
        )
        self.assertEqual(resp2.status_code, 200)
        body2 = resp2.json()
        self.assertTrue(body2.get("ok"), body2)
        self.assertEqual(str(body2.get("interaction_mode") or ""), "expert")
        self.assertEqual(str(body2.get("specialist") or ""), "ops")
        self.assertEqual(str(body2.get("memory_mode") or ""), "store_only")

    def test_messages_use_session_mode_when_payload_omits_mode(self) -> None:
        token = self._login()
        headers = {
            "authorization": f"Bearer {token}",
            "accept": "application/json",
            "content-type": "application/json",
        }
        _ = self.client.post(
            f"/admin/api/chat/sessions/{self.session_id}/mode",
            headers=headers,
            json={"interaction_mode": "expert", "specialist": "ops", "memory_mode": "store_only"},
        )
        resp = self.client.post(
            f"/admin/api/chat/sessions/{self.session_id}/messages",
            headers=headers,
            json={"text": "请总结并发送到项目群"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("ok"), body)
        task_id = str(body.get("task_id") or "")
        self.assertTrue(task_id.strip())
        task = self.store.openclaw_task_get(task_id=task_id, tenant_id=self.tenant_id)
        self.assertIsNotNone(task)
        payload = json.loads(str(task.payload or "{}"))
        self.assertEqual(str(payload.get("interaction_mode") or ""), "expert")
        self.assertEqual(str(payload.get("requested_specialist") or ""), "ops")
        self.assertEqual(str(payload.get("memory_mode") or ""), "store_only")

    def test_admin_dynamic_expert_stats_endpoint(self) -> None:
        token = self._login()
        headers = {
            "authorization": f"Bearer {token}",
            "accept": "application/json",
            "content-type": "application/json",
        }
        _ = self.client.post(
            f"/admin/api/chat/sessions/{self.session_id}/messages",
            headers=headers,
            json={
                "text": "请总结并发送到项目群",
                "interaction_mode": "comprehensive",
                "specialist": "generalist",
            },
        )
        resp = self.client.get(
            "/admin/api/chat/admin/dynamic-expert-stats?limit=200",
            headers={"authorization": f"Bearer {token}", "accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("ok"), body)
        self.assertIn("dynamic_used_count", body)
        self.assertIn("fallback_generalist_count", body)
        self.assertIn("dynamic_used_rate", body)
        self.assertIn("dispatch_reasons", body)
        self.assertIn("dispatch_reason_labels", body)

    def test_admin_dynamic_expert_stats_labels_override_setting(self) -> None:
        token = self._login()
        self.store.set_setting(
            "AIA_DISPATCH_REASON_LABELS_JSON",
            json.dumps(
                {
                    "manager_no_specialist_fallback": {
                        "zh": "自定义回退文案",
                        "en": "Custom fallback label",
                    }
                },
                ensure_ascii=False,
            ),
        )
        headers = {
            "authorization": f"Bearer {token}",
            "accept": "application/json",
            "content-type": "application/json",
        }
        _ = self.client.post(
            f"/admin/api/chat/sessions/{self.session_id}/messages",
            headers=headers,
            json={"text": "请总结并发送到项目群", "interaction_mode": "comprehensive", "specialist": "generalist"},
        )
        resp = self.client.get(
            "/admin/api/chat/admin/dynamic-expert-stats?limit=200",
            headers={"authorization": f"Bearer {token}", "accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("ok"), body)
        labels = body.get("dispatch_reason_labels") or {}
        if "manager_no_specialist_fallback" in labels:
            self.assertEqual(str(labels.get("manager_no_specialist_fallback") or ""), "自定义回退文案")

    def test_admin_dispatch_reason_labels_settings_api_roundtrip(self) -> None:
        token = self._login()
        headers = {
            "authorization": f"Bearer {token}",
            "accept": "application/json",
            "content-type": "application/json",
        }
        set_resp = self.client.post(
            "/admin/api/chat/settings/dispatch-reason-labels",
            headers=headers,
            json={
                "overrides": {
                    "manager_select_failed": {"zh": "自定义总控失败", "en": "Custom manager failed"}
                }
            },
        )
        self.assertEqual(set_resp.status_code, 200)
        set_body = set_resp.json()
        self.assertTrue(set_body.get("ok"), set_body)
        effective = set_body.get("effective") or {}
        row = effective.get("manager_select_failed") or {}
        self.assertEqual(str(row.get("zh") or ""), "自定义总控失败")

        get_resp = self.client.get(
            "/admin/api/chat/settings/dispatch-reason-labels",
            headers={"authorization": f"Bearer {token}", "accept": "application/json"},
        )
        self.assertEqual(get_resp.status_code, 200)
        get_body = get_resp.json()
        self.assertTrue(get_body.get("ok"), get_body)
        overrides = get_body.get("overrides") or {}
        self.assertIn("manager_select_failed", overrides)

    def test_admin_attachment_limits_settings_api_roundtrip(self) -> None:
        token = self._login()
        headers = {
            "authorization": f"Bearer {token}",
            "accept": "application/json",
            "content-type": "application/json",
        }
        get_resp = self.client.get(
            "/admin/api/chat/settings/attachment-limits",
            headers={"authorization": f"Bearer {token}", "accept": "application/json"},
        )
        self.assertEqual(get_resp.status_code, 200)
        get_body = get_resp.json()
        self.assertTrue(get_body.get("ok"), get_body)
        self.assertEqual(int((get_body.get("limits") or {}).get("max_rows_read") or 0), 5000)
        self.assertEqual(int((get_body.get("limits") or {}).get("sql_timeout_ms") or 0), 8000)

        set_resp = self.client.post(
            "/admin/api/chat/settings/attachment-limits",
            headers=headers,
            json={
                "limits": {
                    "max_rows_read": 123,
                    "max_columns": 45,
                    "max_cell_chars": 67,
                    "max_excel_sheets": 8,
                    "large_table_preview_rows": 33,
                    "sql_timeout_ms": 1234,
                }
            },
        )
        self.assertEqual(set_resp.status_code, 200)
        set_body = set_resp.json()
        self.assertTrue(set_body.get("ok"), set_body)
        limits = set_body.get("limits") or {}
        self.assertEqual(int(limits.get("max_rows_read") or 0), 123)
        self.assertEqual(int(limits.get("max_columns") or 0), 45)
        self.assertEqual(int(limits.get("max_cell_chars") or 0), 67)
        self.assertEqual(int(limits.get("max_excel_sheets") or 0), 8)
        self.assertEqual(int(limits.get("large_table_preview_rows") or 0), 33)
        self.assertEqual(int(limits.get("sql_timeout_ms") or 0), 1234)


if __name__ == "__main__":
    unittest.main()

