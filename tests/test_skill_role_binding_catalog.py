from __future__ import annotations

import json
from pathlib import Path

from runtime.skill_role_binding import (
    SKILL_ROLE_BINDING_ENABLED_SETTING,
    SKILL_ROLE_BINDING_KEY,
    normalize_skill_role_binding,
    ordered_binding_roles,
    skill_role_binding_enabled,
    skill_role_binding_enabled_env_present,
    skill_role_binding_enabled_stored,
)
from runtime.skills_prompt import collect_skill_catalog_entries
from runtime.skills_workspace_lane import skill_dir_private_lane_segment
from svc.persistence.sqlite_store import SqliteStore
from runtime.tools.catalog import default_registry


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
    _write_skill(skills_root / "_workspace" / "public", "skill-public")

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
    assert "skill-public" in names


def test_skill_dir_private_lane_segment_role_and_legacy_agent(tmp_path: Path) -> None:
    home = tmp_path / "skills"
    role_skill = home / "_workspace" / "ops" / "demo-skill"
    role_skill.mkdir(parents=True)
    assert skill_dir_private_lane_segment(role_skill, skills_home=home) == "ops"
    leg = home / "_workspace" / "_agent" / "sess" / "legacy-skill"
    leg.mkdir(parents=True)
    assert skill_dir_private_lane_segment(leg, skills_home=home) == "sess"
    flat = home / "_workspace" / "flat-only"
    flat.mkdir(parents=True)
    assert skill_dir_private_lane_segment(flat, skills_home=home) is None


def test_collect_includes_own_private_lane_without_role_mapping(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    skills_root = tmp_path / "skills_priv"
    skills_root.mkdir(parents=True, exist_ok=True)
    lane = "generalist"
    _write_skill(skills_root / "_workspace" / lane, "lane-bound-skill")
    monkeypatch.setenv("AIA_SKILLS_ROOT", str(skills_root))
    store.set_setting(SKILL_ROLE_BINDING_ENABLED_SETTING, "1")
    mapping = {r: [] for r in ordered_binding_roles()}
    mapping["generalist"] = ["other-only"]
    store.set_setting(SKILL_ROLE_BINDING_KEY, json.dumps(mapping))

    reg = default_registry(store=store)
    entries = collect_skill_catalog_entries(
        store=store,
        registry=reg,
        base_url="",
        skill_binding_role="generalist",
        exclude_foreign_private_workspace_skills=True,
        private_workspace_lane_segment=lane,
    )
    names = {e[0] for e in entries}
    assert "lane-bound-skill" in names


def test_collect_when_binding_enabled_empty_mapping_shows_only_public(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    skills_root = tmp_path / "skills_empty_bind"
    skills_root.mkdir(parents=True, exist_ok=True)
    _write_skill(skills_root, "skill-root-only")
    _write_skill(skills_root / "_workspace" / "public", "skill-public")

    monkeypatch.setenv("AIA_SKILLS_ROOT", str(skills_root))
    store.set_setting(SKILL_ROLE_BINDING_ENABLED_SETTING, "1")
    store.set_setting(SKILL_ROLE_BINDING_KEY, "{}")

    reg = default_registry(store=store)
    entries = collect_skill_catalog_entries(
        store=store,
        registry=reg,
        base_url="",
        skill_binding_role="generalist",
    )
    names = {e[0] for e in entries}
    assert "skill-public" in names
    assert "skill-root-only" not in names


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
    assert "solo-skill" in names


def test_normalize_drops_unknown_skills(tmp_path: Path) -> None:
    roles = ["manager", "generalist"]
    out = normalize_skill_role_binding(
        mapping_raw={"manager": ["nope", "skill-x"], "generalist": ["skill-x"]},
        valid_skill_names={"skill-x"},
        available_roles=roles,
    )
    assert out["manager"] == ["skill-x"]
    assert out["generalist"] == ["skill-x"]


def test_skill_role_binding_env_overrides_store_value(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "rolebind.sqlite"
    store = SqliteStore(str(db))
    store.set_setting(SKILL_ROLE_BINDING_ENABLED_SETTING, "1")
    monkeypatch.setenv("AIA_SKILL_ROLE_BINDING_ENABLED", "0")
    assert skill_role_binding_enabled_env_present() is True
    assert skill_role_binding_enabled_stored(store=store) is True
    assert skill_role_binding_enabled(store=store) is False
