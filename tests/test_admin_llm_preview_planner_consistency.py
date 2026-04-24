from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.tools.exposure_plan import build_llm_tools_plan


class AdminLLMPreviewPlannerConsistencyTests(unittest.TestCase):
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
        r = self.client.post(
            "/admin/api/auth/login",
            json={"tenant_id": self.tenant_id, "username": "administrator", "password": "test-admin-pass", "purpose": "console"},
        )
        self.token = str((r.json() or {}).get("token") or "")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _h(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}"}

    @staticmethod
    def _tool_names(rows: list[dict]) -> list[str]:
        out: list[str] = []
        for ent in rows:
            if not isinstance(ent, dict) or str(ent.get("type") or "") != "function":
                continue
            fn = ent.get("function")
            if not isinstance(fn, dict):
                continue
            nm = str(fn.get("name") or "").strip()
            if nm:
                out.append(nm)
        return sorted(out)

    def test_preview_matches_planner(self) -> None:
        role = "generalist"
        api = self.client.get(f"/admin/api/tools/llm/preview?role={role}", headers=self._h())
        self.assertEqual(api.status_code, 200, api.text)
        body = api.json() or {}
        self.assertTrue(body.get("ok"))

        plan = build_llm_tools_plan(
            store=self.store,
            role=role,
            base_url=None,
            max_json_bytes=None,
            include_mcp=True,
            preview_internal=True,
        )
        api_names = self._tool_names(list(body.get("tools_wired") or []))
        plan_names = self._tool_names(list(plan.tools_wired or []))
        self.assertEqual(api_names, plan_names)


if __name__ == "__main__":
    unittest.main()

