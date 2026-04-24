from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from oclaw.openclaw_runtime.skills import discover_workspace_skill_manifests
from oclaw.tools.skills_runtime.materialize_skill_tools import materialize_executable_skill_tools


class SkillRuntimeMetadataAndToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.skills_root = Path(self._tmp.name) / "skills"
        self.skills_root.mkdir(parents=True, exist_ok=True)
        os.environ["AIA_SKILLS_ROOT"] = str(self.skills_root)

    def tearDown(self) -> None:
        os.environ.pop("AIA_SKILLS_ROOT", None)
        self._tmp.cleanup()

    def test_manifest_parses_runtime_spec(self) -> None:
        d = self.skills_root / "demo_runtime"
        d.mkdir(parents=True, exist_ok=True)
        (d / "scripts").mkdir(parents=True, exist_ok=True)
        (d / "scripts" / "run.py").write_text("print('{\"ok\": true}')\n", encoding="utf-8")
        (d / "SKILL.md").write_text(
            "---\n"
            "name: demo_runtime\n"
            "description: demo\n"
            "metadata:\n"
            "  openclaw:\n"
            "    runtime:\n"
            "      type: python\n"
            "      entry: scripts/run.py\n"
            "      schema:\n"
            "        type: object\n"
            "        properties:\n"
            "          input_path: { type: string }\n"
            "        additionalProperties: false\n"
            "---\n"
            "\n"
            "# demo\n",
            encoding="utf-8",
        )
        ms = discover_workspace_skill_manifests()
        m = next((x for x in ms if x.name == "demo_runtime"), None)
        assert m is not None
        assert isinstance(m.runtime, dict)
        assert m.runtime.get("type") == "python"
        assert m.runtime.get("entry") == "scripts/run.py"
        assert isinstance(m.runtime.get("schema"), dict)

    def test_materialize_creates_tool_for_runtime_skill(self) -> None:
        d = self.skills_root / "demo_runtime_tool"
        d.mkdir(parents=True, exist_ok=True)
        (d / "scripts").mkdir(parents=True, exist_ok=True)
        (d / "scripts" / "run.py").write_text("print('{\"ok\": true}')\n", encoding="utf-8")
        (d / "SKILL.md").write_text(
            "---\n"
            "name: demo_runtime_tool\n"
            "description: demo\n"
            "metadata:\n"
            "  openclaw:\n"
            "    runtime:\n"
            "      type: python\n"
            "      entry: scripts/run.py\n"
            "---\n",
            encoding="utf-8",
        )
        tools = materialize_executable_skill_tools(store=None)
        names = {t.name for t in tools}
        assert "demo_runtime_tool" in names


if __name__ == "__main__":
    unittest.main()

