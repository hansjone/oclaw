from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from oclaw.runtime.tools.skills_runtime.subprocess_exec import run_skill_runtime_entry


class SkillRuntimeRestrictedFsPermissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.skill_dir = Path(self._tmp.name) / "skill"
        self.skill_dir.mkdir(parents=True, exist_ok=True)
        (self.skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
        (self.skill_dir / "scripts" / "ok.py").write_text("print('{\"ok\": true}')\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_fs_write_disabled_blocks_output_path(self) -> None:
        res = run_skill_runtime_entry(
            skill_name="demo",
            skill_dir=str(self.skill_dir),
            runtime={"type": "python", "entry": "scripts/ok.py", "permissions": {"fs_write": False}},
            args={"output_path": "out.txt"},
        )
        self.assertFalse(res.get("ok"))
        self.assertEqual(str(res.get("error_code")), "path_restricted")
        self.assertIn("fs_write_disabled", str(res.get("error") or ""))


if __name__ == "__main__":
    unittest.main()

