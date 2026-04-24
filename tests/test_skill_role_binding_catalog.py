from __future__ import annotations

import json
from pathlib import Path

from oclaw.runtime.skill_role_binding import (
    SKILL_ROLE_BINDING_ENABLED_SETTING,
    SKILL_ROLE_BINDING_KEY,
    normalize_skill_role_binding,
    ordered_binding_roles,
)
from oclaw.runtime.skills_prompt import collect_skill_catalog_entries
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.tools.catalog import default_registry


def _write_skill(root: Path, name: str) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test {name}\nmetadata: {{}}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def test_collect_respects_role_binding_union(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    skills_root = tmp_path / "skills"
    skills_root.mkdir(parents=True, exist_ok=True)
    _write_skill(skills_root, "skill-alpha")
    _write_skill(skills_root, "skill-beta")

    monkeypatch.setenv("AIA_SKILLS_ROOT", str(skills_root))
    store.set_setting(SKILL_ROLE_BINDING_ENABLED_SETTING, "1")
    mapping = {r: [] for r in ordered_binding_roles()}
    mapping["generalist"] = ["skill-alpha"]
    mapping["manager"] = ["skill-beta"]
    store.set_setting(SKILL_ROLE_BINDING_KEY, json.dumps(mapping))

    reg = default_registry(store=store)
    entries = collect_skill_catalog_entries(
        store=store,
        registry=reg,
        base_url="",
        skill_binding_role="generalist",
    )
    names = {e[0] for e in entries}
    assert "skill-alpha" in names
    assert "skill-beta" in names


def test_collect_unfiltered_when_binding_disabled(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    skills_root = tmp_path / "skills2"
    skills_root.mkdir(parents=True, exist_ok=True)
    _write_skill(skills_root, "solo-skill")
    monkeypatch.setenv("AIA_SKILLS_ROOT", str(skills_root))
    store.set_setting(SKILL_ROLE_BINDING_ENABLED_SETTING, "0")
    store.set_setting(SKILL_ROLE_BINDING_KEY, json.dumps({"generalist": ["solo-skill"]}))

    reg = default_registry(store=store)
    entries = collect_skill_catalog_entries(
        store=store,
        registry=reg,
        base_url="",
        skill_binding_role="generalist",
    )
    names = {e[0] for e in entries}
    assert "solo-skill" not in names


def test_normalize_drops_unknown_skills(tmp_path: Path) -> None:
    roles = ["manager", "generalist"]
    out = normalize_skill_role_binding(
        mapping_raw={"manager": ["nope", "skill-x"], "generalist": ["skill-x"]},
        valid_skill_names={"skill-x"},
        available_roles=roles,
    )
    assert out["manager"] == ["skill-x"]
    assert out["generalist"] == ["skill-x"]
