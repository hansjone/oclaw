from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.platform.persistence.sqlite_store import SqliteStore


class AdminSkillsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ops.sqlite"
        self.skills_root = Path(self._tmp.name) / "skills"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["OPS_ASSISTANT_PASSWORD"] = "test-admin-pass"
        os.environ["AIA_SKILLS_ROOT"] = str(self.skills_root)
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
        os.environ.pop("AIA_SKILLS_ROOT", None)
        self._tmp.cleanup()

    def _h(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}"}

    def test_skills_create_list_disable_enable(self) -> None:
        c = self.client.post(
            "/admin/api/skills/create",
            json={"name": "api_skill_demo", "description": "demo from api", "body_markdown": "# hi"},
            headers=self._h(),
        )
        self.assertEqual(c.status_code, 200, c.text)
        self.assertTrue((c.json() or {}).get("ok"))

        ls = self.client.get("/admin/api/skills", headers=self._h())
        self.assertEqual(ls.status_code, 200, ls.text)
        items = (ls.json() or {}).get("items") or []
        self.assertTrue(any(str(x.get("name") or "") == "api_skill_demo" for x in items))
        one = next((x for x in items if str(x.get("name") or "") == "api_skill_demo"), {})
        self.assertIn("runtime", one)
        self.assertIn("executable", one)

        d = self.client.post("/admin/api/skills/disable", json={"name": "api_skill_demo"}, headers=self._h())
        self.assertEqual(d.status_code, 200, d.text)
        self.assertTrue((d.json() or {}).get("ok"))
        e = self.client.post("/admin/api/skills/enable", json={"name": "api_skill_demo"}, headers=self._h())
        self.assertEqual(e.status_code, 200, e.text)
        self.assertTrue((e.json() or {}).get("ok"))

    def test_skills_install_registry_archive(self) -> None:
        pkg = Path(self._tmp.name) / "pkg"
        d = pkg / "demo"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text("name: reg_api_skill\ndescription: demo\n", encoding="utf-8")
        z = Path(self._tmp.name) / "demo.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.write(d / "SKILL.md", arcname="demo/SKILL.md")
        r = self.client.post(
            "/admin/api/skills/install-registry",
            json={"archive_url": z.resolve().as_uri()},
            headers=self._h(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue((r.json() or {}).get("ok"))

    def test_skills_binding_get_and_save(self) -> None:
        c = self.client.post(
            "/admin/api/skills/create",
            json={"name": "bind_demo_skill", "description": "for binding test", "body_markdown": "# t"},
            headers=self._h(),
        )
        self.assertEqual(c.status_code, 200, c.text)
        g = self.client.get("/admin/api/skills/binding", headers=self._h())
        self.assertEqual(g.status_code, 200, g.text)
        body = g.json() or {}
        self.assertTrue(body.get("ok"))
        self.assertIn("available_roles", body)
        self.assertIn("mapping", body)
        roles = list(body.get("available_roles") or [])
        self.assertIn("manager", roles)
        mapping = dict(body.get("mapping") or {})
        for r in roles:
            mapping.setdefault(r, [])
        mapping["generalist"] = ["bind_demo_skill"]
        mapping["manager"] = ["bind_demo_skill"]
        s = self.client.post(
            "/admin/api/skills/binding",
            json={"enabled": True, "mapping": mapping},
            headers=self._h(),
        )
        self.assertEqual(s.status_code, 200, s.text)
        sb = s.json() or {}
        self.assertTrue(sb.get("ok"))
        self.assertTrue(sb.get("enabled"))
        self.assertIn("bind_demo_skill", (sb.get("mapping") or {}).get("generalist", []))

    def test_skills_effective_dashboard(self) -> None:
        c = self.client.post(
            "/admin/api/skills/create",
            json={"name": "effective_demo_skill", "description": "for effective dashboard", "body_markdown": "# t"},
            headers=self._h(),
        )
        self.assertEqual(c.status_code, 200, c.text)
        b = self.client.post(
            "/admin/api/skills/binding",
            json={
                "enabled": True,
                "mapping": {
                    "manager": ["effective_demo_skill"],
                    "generalist": [],
                    "ops": [],
                    "image": [],
                    "memory_curator": [],
                },
            },
            headers=self._h(),
        )
        self.assertEqual(b.status_code, 200, b.text)
        r = self.client.get("/admin/api/skills/effective", headers=self._h())
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json() or {}
        self.assertTrue(body.get("ok"))
        items = list(body.get("items") or [])
        self.assertTrue(any(str(x.get("role") or "") == "manager" for x in items))
        mgr = next((x for x in items if str(x.get("role") or "") == "manager"), {})
        self.assertGreaterEqual(int(mgr.get("workspace_total") or 0), 1)
        self.assertGreaterEqual(int(mgr.get("total") or 0), int(mgr.get("workspace_total") or 0))
        self.assertIn("workspace_docs_only", mgr)
        self.assertIn("workspace_resolved_tool_match", mgr)

    def test_skills_retry_install_registry(self) -> None:
        pkg = Path(self._tmp.name) / "pkg2"
        d = pkg / "demo2"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text("name: reg_retry_skill\ndescription: demo\n", encoding="utf-8")
        z = Path(self._tmp.name) / "demo2.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.write(d / "SKILL.md", arcname="demo2/SKILL.md")
        r = self.client.post(
            "/admin/api/skills/retry-install",
            json={"source": "registry", "target": z.resolve().as_uri()},
            headers=self._h(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue((r.json() or {}).get("ok"))


if __name__ == "__main__":
    unittest.main()

