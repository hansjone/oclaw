from __future__ import annotations

from pathlib import Path

from runtime.skills import build_skill_manifest, discover_workspace_skill_manifests, load_skill_manifest
from runtime.tools.base import ToolRegistry, ToolSpec


def test_load_skill_manifest_with_oclaw_metadata(tmp_path: Path) -> None:
    d = tmp_path / "skills" / "demo"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        """---
name: demo
description: demo skill
user-invocable: true
disable-model-invocation: false
metadata: {"oclaw":{"install":[{"id":"i1","kind":"node","package":"foo"}]}}
---

# Demo
""",
        encoding="utf-8",
    )
    m = load_skill_manifest(d)
    assert m is not None
    assert m.name == "demo"
    assert m.description == "demo skill"
    assert len(m.install) == 1
    assert m.install[0].kind == "node"


def test_discover_workspace_skill_manifests(tmp_path: Path) -> None:
    base = tmp_path / "skills"
    (base / "a").mkdir(parents=True, exist_ok=True)
    (base / "a" / "SKILL.md").write_text("name: a\ndescription: A", encoding="utf-8")
    rows = discover_workspace_skill_manifests(base)
    assert len(rows) == 1
    assert rows[0].name == "a"


def test_skill_manifest_is_deterministic_and_sorted() -> None:
    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

    reg = ToolRegistry(
        [
            ToolSpec(name="z_tool", description="z", parameters={"type": "object"}, handler=lambda _a: {"ok": True}),
            ToolSpec(name="a_tool", description="a", parameters={"type": "object"}, handler=lambda _a: {"ok": True}),
        ]
    )
    skills1, stats1 = build_skill_manifest(registry=reg, store=Store(), base_url="")
    skills2, stats2 = build_skill_manifest(registry=reg, store=Store(), base_url="")
    assert [s.name for s in skills1] == ["a_tool", "z_tool"]
    assert [s.name for s in skills2] == ["a_tool", "z_tool"]
    assert stats1.get("visible_names_preview") == stats2.get("visible_names_preview")

