from __future__ import annotations

from pathlib import Path

from oclaw.platform.config.paths import PROJECT_ROOT


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_main_dynamic_placeholder_only_in_role_system() -> None:
    root = (PROJECT_ROOT / "runtime" / "workspaces" / "main").resolve()
    role_system = _read(root / "ROLE_SYSTEM.md")
    soul = _read(root / "SOUL.md")
    assert "{{MANAGER_DYNAMIC_EXPERTS_HINT}}" in role_system
    assert "{{" not in soul
    for name in ("AGENTS.md", "IDENTITY.md", "USER.md"):
        p = root / name
        if p.exists():
            assert "{{" not in _read(p)


def test_main_hard_routing_rule_only_in_role_system() -> None:
    root = (PROJECT_ROOT / "runtime" / "workspaces" / "main").resolve()
    role_system = _read(root / "ROLE_SYSTEM.md")
    assert "回退 `generalist`" in role_system
    for name in ("AGENTS.md", "IDENTITY.md", "USER.md", "SOUL.md"):
        p = root / name
        if p.exists():
            assert "回退 `generalist`" not in _read(p)


def test_every_workspace_has_role_system() -> None:
    root = (PROJECT_ROOT / "runtime" / "workspaces").resolve()
    for item in root.iterdir():
        if not item.is_dir():
            continue
        if item.name.startswith("__"):
            continue
        # `_system` holds template fragments/snippets, not routed specialist workspaces.
        if item.name.startswith("_"):
            continue
        assert (item / "ROLE_SYSTEM.md").exists(), f"missing ROLE_SYSTEM.md for {item.name}"


def test_workspace_legacy_prompt_files_removed() -> None:
    root = (PROJECT_ROOT / "runtime" / "workspaces").resolve()
    legacy = ("AGENTS.md", "IDENTITY.md", "USER.md")
    for item in root.iterdir():
        if not item.is_dir():
            continue
        if item.name.startswith("__"):
            continue
        if item.name.startswith("_"):
            continue
        for name in legacy:
            assert not (item / name).exists(), f"legacy prompt file still exists: {item.name}/{name}"
