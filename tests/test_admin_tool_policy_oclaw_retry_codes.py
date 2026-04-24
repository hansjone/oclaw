from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore


class AdminToolPolicyOclawRetryCodesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ops.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["OPS_ASSISTANT_PASSWORD"] = "test-admin-pass"
        self.store = SqliteStore(str(self.db))
        t = self.store.create_tenant("Team")
        self.tenant_id = str(t["id"])
        self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash=hashlib.sha256("test-admin-pass".encode("utf-8")).hexdigest(),
            is_active=True,
        )
        self.client = TestClient(create_app())
        self.client.post("/admin/api/auth/bootstrap", json={})

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _login(self) -> str:
        r = self.client.post(
            "/admin/api/auth/login",
            json={"tenant_id": self.tenant_id, "username": "administrator", "password": "test-admin-pass", "purpose": "console"},
        )
        body = r.json()
        self.assertTrue(body.get("ok"), body)
        return str(body.get("token") or "")

    def test_tool_policy_get_and_save_oclaw_retry_codes(self) -> None:
        token = self._login()
        headers = {"authorization": f"Bearer {token}"}
        r1 = self.client.get("/admin/api/tool-policy", headers=headers)
        self.assertEqual(r1.status_code, 200)
        b1 = r1.json()
        self.assertTrue(b1.get("ok"))
        self.assertTrue(str(b1.get("oclaw_retryable_error_codes") or "").strip())
        self.assertFalse(bool(b1.get("oclaw_retry_codes_strict_mode")))

        payload = {
            "turn_max_tool_workers": 8,
            "turn_max_tool_rounds": 8,
            "turn_max_context_messages": 80,
            "sse_queue_maxsize": 2000,
            "tool_log_max_chars": 200000,
            "enable_mcp_tools": True,
            "enable_plugin_tools": False,
            "tool_llm_message_max_chars": 0,
            "mcp_filesystem_extra_roots": "",
            "mcp_env_allowlist": "",
            "oclaw_retryable_error_codes": "provider_timeout, context_overflow",
            "oclaw_retry_codes_strict_mode": False,
            "wecom_longconn_workers": 2,
            "wecom_longconn_inbound_queue_maxsize": 200,
        }
        r2 = self.client.post("/admin/api/tool-policy", json=payload, headers=headers)
        self.assertEqual(r2.status_code, 200)
        b2 = r2.json()
        self.assertTrue(b2.get("ok"))
        self.assertEqual(str(b2.get("oclaw_retryable_error_codes") or ""), "provider_timeout,context_overflow")
        self.assertFalse(bool(b2.get("oclaw_retry_codes_strict_mode")))
        self.assertEqual(list(b2.get("unknown_retryable_error_codes") or []), [])

    def test_tool_policy_retry_codes_unknown_filtered(self) -> None:
        token = self._login()
        headers = {"authorization": f"Bearer {token}"}
        payload = {
            "turn_max_tool_workers": 8,
            "turn_max_tool_rounds": 8,
            "turn_max_context_messages": 80,
            "sse_queue_maxsize": 2000,
            "tool_log_max_chars": 200000,
            "enable_mcp_tools": True,
            "enable_plugin_tools": False,
            "tool_llm_message_max_chars": 0,
            "mcp_filesystem_extra_roots": "",
            "mcp_env_allowlist": "",
            "oclaw_retryable_error_codes": "provider_timeout, typo_code_x, context_overflow",
            "oclaw_retry_codes_strict_mode": False,
            "wecom_longconn_workers": 2,
            "wecom_longconn_inbound_queue_maxsize": 200,
        }
        r = self.client.post("/admin/api/tool-policy", json=payload, headers=headers)
        self.assertEqual(r.status_code, 200)
        b = r.json()
        self.assertTrue(b.get("ok"))
        self.assertEqual(str(b.get("oclaw_retryable_error_codes") or ""), "provider_timeout,context_overflow")
        self.assertEqual(list(b.get("unknown_retryable_error_codes") or []), ["typo_code_x"])

    def test_tool_policy_retry_codes_unknown_rejected_in_strict_mode(self) -> None:
        token = self._login()
        headers = {"authorization": f"Bearer {token}"}
        payload = {
            "turn_max_tool_workers": 8,
            "turn_max_tool_rounds": 8,
            "turn_max_context_messages": 80,
            "sse_queue_maxsize": 2000,
            "tool_log_max_chars": 200000,
            "enable_mcp_tools": True,
            "enable_plugin_tools": False,
            "tool_llm_message_max_chars": 0,
            "mcp_filesystem_extra_roots": "",
            "mcp_env_allowlist": "",
            "oclaw_retryable_error_codes": "provider_timeout, typo_code_x",
            "oclaw_retry_codes_strict_mode": True,
            "wecom_longconn_workers": 2,
            "wecom_longconn_inbound_queue_maxsize": 200,
        }
        r = self.client.post("/admin/api/tool-policy", json=payload, headers=headers)
        self.assertEqual(r.status_code, 400)
        b = r.json()
        self.assertIn("detail", b)
        detail = b["detail"]
        self.assertEqual(str(detail.get("code") or ""), "invalid_retryable_error_codes")
        self.assertEqual(list(detail.get("unknown_retryable_error_codes") or []), ["typo_code_x"])


if __name__ == "__main__":
    unittest.main()

