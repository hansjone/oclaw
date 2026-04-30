from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

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

    def test_skills_uninstall(self) -> None:
        c = self.client.post(
            "/admin/api/skills/create",
            json={"name": "to_remove_skill", "description": "remove me", "body_markdown": "# remove"},
            headers=self._h(),
        )
        self.assertEqual(c.status_code, 200, c.text)
        self.assertTrue((c.json() or {}).get("ok"))
        u = self.client.post("/admin/api/skills/uninstall", json={"name": "to_remove_skill"}, headers=self._h())
        self.assertEqual(u.status_code, 200, u.text)
        self.assertTrue((u.json() or {}).get("ok"))
        ls = self.client.get("/admin/api/skills", headers=self._h())
        self.assertEqual(ls.status_code, 200, ls.text)
        items = (ls.json() or {}).get("items") or []
        self.assertFalse(any(str(x.get("name") or "") == "to_remove_skill" for x in items))

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

    def test_skills_mode_get_and_save(self) -> None:
        g = self.client.get("/admin/api/skills/mode", headers=self._h())
        self.assertEqual(g.status_code, 200, g.text)
        gb = g.json() or {}
        self.assertTrue(gb.get("ok"))
        self.assertIn("market_provider", gb)
        self.assertIn(str(gb.get("market_provider") or ""), {"clawhub", "cocoloop"})
        s = self.client.post(
            "/admin/api/skills/mode",
            json={"prompt_in_system": True, "toolcall_enabled": False, "market_provider": "cocoloop"},
            headers=self._h(),
        )
        self.assertEqual(s.status_code, 200, s.text)
        sb = s.json() or {}
        self.assertTrue(sb.get("ok"))
        self.assertTrue(bool(sb.get("prompt_in_system")))
        self.assertFalse(bool(sb.get("toolcall_enabled")))
        self.assertEqual(str(sb.get("market_provider") or ""), "cocoloop")
        g2 = self.client.get("/admin/api/skills/mode", headers=self._h())
        self.assertEqual((g2.json() or {}).get("market_provider"), "cocoloop")

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
                    "memory": [],
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

    def test_workspace_skill_create_test_run_and_failure_feedback(self) -> None:
        c = self.client.post(
            "/admin/api/skills/create-workspace",
            json={"name": "ws_demo_skill", "description": "workspace demo", "runtime_type": "python"},
            headers=self._h(),
        )
        self.assertEqual(c.status_code, 200, c.text)
        body = c.json() or {}
        self.assertTrue(body.get("ok"))
        result_create = body.get("result") if isinstance(body.get("result"), dict) else {}
        self.assertIn("auto_enabled", result_create)
        self.assertIn("binding_applied_roles", result_create)

        r1 = self.client.post(
            "/admin/api/skills/test-run",
            json={"name": "ws_demo_skill", "args": {"hello": "world"}},
            headers=self._h(),
        )
        self.assertEqual(r1.status_code, 200, r1.text)
        result1 = ((r1.json() or {}).get("result") or {})
        self.assertTrue(bool(result1.get("ok")))
        self.assertIn("result", result1)

        # fs_write is disabled by template; write-like arg should be rejected and return classified failure.
        r2 = self.client.post(
            "/admin/api/skills/test-run",
            json={"name": "ws_demo_skill", "args": {"output_path": "../escape.txt"}},
            headers=self._h(),
        )
        self.assertEqual(r2.status_code, 200, r2.text)
        result2 = ((r2.json() or {}).get("result") or {})
        self.assertFalse(bool(result2.get("ok")))
        self.assertIn(str(result2.get("error_code") or ""), {"path_restricted", "runtime_error"})

    def test_skills_self_check_endpoint(self) -> None:
        c = self.client.post(
            "/admin/api/skills/create-workspace",
            json={"name": "ws_selfcheck_skill", "description": "workspace selfcheck", "runtime_type": "python"},
            headers=self._h(),
        )
        self.assertEqual(c.status_code, 200, c.text)
        self.assertTrue((c.json() or {}).get("ok"))
        r = self.client.get("/admin/api/skills/self-check", headers=self._h())
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json() or {}
        self.assertTrue(body.get("ok"))
        self.assertGreaterEqual(int(body.get("skills_total") or 0), 1)
        self.assertGreaterEqual(int(body.get("executable_total") or 0), 1)
        self.assertIn("invalid_runtime_entries", body)
        self.assertIn("classification_counts", body)

    def test_skills_self_check_with_execution_and_classification(self) -> None:
        c = self.client.post(
            "/admin/api/skills/create-workspace",
            json={"name": "ws_selfcheck_exec_skill", "description": "workspace selfcheck exec", "runtime_type": "python"},
            headers=self._h(),
        )
        self.assertEqual(c.status_code, 200, c.text)
        self.assertTrue((c.json() or {}).get("ok"))
        skill_dir = self.skills_root / "_workspace" / "ws_selfcheck_exec_skill"
        run_py = skill_dir / "scripts" / "run.py"
        run_py.write_text("print('x' * 5000)\n", encoding="utf-8")
        skill_md = skill_dir / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        content = content.replace('"permissions": {"fs_write": false, "net": false, "process": true}', '"permissions": {"fs_write": false, "net": false, "process": true}, "max_output_bytes": 1024')
        skill_md.write_text(content, encoding="utf-8")

        r = self.client.get("/admin/api/skills/self-check?include_execution=true", headers=self._h())
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json() or {}
        self.assertTrue(body.get("ok"))
        self.assertTrue(bool(body.get("execution_checked")))
        self.assertGreaterEqual(int(body.get("execution_checked_total") or 0), 1)
        counts = body.get("classification_counts") if isinstance(body.get("classification_counts"), dict) else {}
        self.assertGreaterEqual(int(counts.get("output_truncated") or 0), 1)

    def test_market_install_uses_adapter_and_installs(self) -> None:
        pkg = Path(self._tmp.name) / "pkg3"
        d = pkg / "demo3"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text("name: market_adapter_skill\ndescription: demo\n", encoding="utf-8")
        z = Path(self._tmp.name) / "demo3.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.write(d / "SKILL.md", arcname="demo3/SKILL.md")

        class _FakeAdapter:
            provider = "clawhub"

            def search(self, query: str, *, limit: int = 20):
                _ = (query, limit)
                return [{"slug": "owner/demo3", "name": "demo3"}]

            def detail(self, slug: str):
                _ = slug
                return {"slug": "owner/demo3", "latestVersion": "1.0.0"}

            def resolve_archive_url(self, *, slug: str, version: str | None = None):
                _ = (slug, version)
                return z.resolve().as_uri(), "1.0.0"

        with patch("oclaw.interfaces.admin.skills_api.get_market_adapter", return_value=_FakeAdapter()):
            r = self.client.post(
                "/admin/api/skills/market/install",
                json={"slug": "owner/demo3"},
                headers=self._h(),
            )
            self.assertEqual(r.status_code, 200, r.text)
            rb = r.json() or {}
            self.assertTrue(rb.get("ok"))
            installed_name = str(((rb.get("result") or {}).get("name") or "")).strip()
            self.assertTrue(installed_name)

            ls = self.client.get("/admin/api/skills", headers=self._h())
            self.assertEqual(ls.status_code, 200, ls.text)
            items = (ls.json() or {}).get("items") or []
            self.assertTrue(any(str(x.get("name") or "") == installed_name for x in items))

    def test_workspace_skill_real_task_style_roundtrip(self) -> None:
        c = self.client.post(
            "/admin/api/skills/create-workspace",
            json={"name": "ws_task_skill", "description": "task style", "runtime_type": "python"},
            headers=self._h(),
        )
        self.assertEqual(c.status_code, 200, c.text)
        self.assertTrue((c.json() or {}).get("ok"))

        # Replace template runtime script with a task-like implementation.
        skill_script = self.skills_root / "_workspace" / "ws_task_skill" / "scripts" / "run.py"
        skill_script.write_text(
            "import json\n"
            "import sys\n\n"
            "def main():\n"
            "    payload = json.loads(sys.stdin.read() or '{}')\n"
            "    args = payload.get('args') or {}\n"
            "    text = str(args.get('text') or '')\n"
            "    words = [w for w in text.strip().split(' ') if w]\n"
            "    out = {\n"
            "        'ok': True,\n"
            "        'word_count': len(words),\n"
            "        'upper': text.upper(),\n"
            "        'contains_number': any(ch.isdigit() for ch in text),\n"
            "    }\n"
            "    print(json.dumps(out, ensure_ascii=False))\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n",
            encoding="utf-8",
        )

        r = self.client.post(
            "/admin/api/skills/test-run",
            json={"name": "ws_task_skill", "args": {"text": "oclaw skill 2026"}},
            headers=self._h(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        result = ((r.json() or {}).get("result") or {})
        self.assertTrue(bool(result.get("ok")))
        parsed = result.get("result") if isinstance(result.get("result"), dict) else {}
        self.assertEqual(int(parsed.get("word_count") or 0), 3)
        self.assertEqual(str(parsed.get("upper") or ""), "OCLAW SKILL 2026")
        self.assertTrue(bool(parsed.get("contains_number")))

    def test_workspace_skill_failure_classification_timeout(self) -> None:
        c = self.client.post(
            "/admin/api/skills/create-workspace",
            json={"name": "ws_timeout_skill", "description": "timeout test", "runtime_type": "python"},
            headers=self._h(),
        )
        self.assertEqual(c.status_code, 200, c.text)
        self.assertTrue((c.json() or {}).get("ok"))
        skill_dir = self.skills_root / "_workspace" / "ws_timeout_skill"
        skill_md = skill_dir / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        content = content.replace('"permissions": {"fs_write": false, "net": false, "process": true}', '"permissions": {"fs_write": false, "net": false, "process": true}, "timeout_s": 1')
        skill_md.write_text(content, encoding="utf-8")
        run_py = skill_dir / "scripts" / "run.py"
        run_py.write_text(
            "import json\nimport sys\nimport time\n\n"
            "def main():\n"
            "    _ = json.loads(sys.stdin.read() or '{}')\n"
            "    time.sleep(2)\n"
            "    print(json.dumps({'ok': True}, ensure_ascii=False))\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n",
            encoding="utf-8",
        )
        r = self.client.post(
            "/admin/api/skills/test-run",
            json={"name": "ws_timeout_skill", "args": {}},
            headers=self._h(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        result = ((r.json() or {}).get("result") or {})
        self.assertFalse(bool(result.get("ok")))
        self.assertEqual(str(result.get("error_code") or ""), "timeout")

    def test_workspace_skill_failure_classification_output_limit(self) -> None:
        c = self.client.post(
            "/admin/api/skills/create-workspace",
            json={"name": "ws_output_skill", "description": "output limit test", "runtime_type": "python"},
            headers=self._h(),
        )
        self.assertEqual(c.status_code, 200, c.text)
        self.assertTrue((c.json() or {}).get("ok"))
        skill_dir = self.skills_root / "_workspace" / "ws_output_skill"
        skill_md = skill_dir / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        content = content.replace('"permissions": {"fs_write": false, "net": false, "process": true}', '"permissions": {"fs_write": false, "net": false, "process": true}, "max_output_bytes": 128')
        skill_md.write_text(content, encoding="utf-8")
        run_py = skill_dir / "scripts" / "run.py"
        run_py.write_text(
            "import json\nimport sys\n\n"
            "def main():\n"
            "    _ = json.loads(sys.stdin.read() or '{}')\n"
            "    print('x' * 4096)\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n",
            encoding="utf-8",
        )
        r = self.client.post(
            "/admin/api/skills/test-run",
            json={"name": "ws_output_skill", "args": {}},
            headers=self._h(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        result = ((r.json() or {}).get("result") or {})
        self.assertTrue("stdout" in result)
        self.assertLessEqual(len(str(result.get("stdout") or "")), 1024)


if __name__ == "__main__":
    unittest.main()

