from __future__ import annotations

from pathlib import Path

import pytest

from runtime.agent_context import loader as loader_mod


def _set_project_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(loader_mod, "PROJECT_ROOT", tmp_path)


def test_build_role_system_context_reads_runtime_workspaces(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_project_root(monkeypatch, tmp_path)
    ws = tmp_path / "runtime" / "workspaces" / "main"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "SOUL.md").write_text("main soul", encoding="utf-8")
    (ws / "ROLE_SYSTEM.md").write_text("main role system", encoding="utf-8")
    out = loader_mod.build_role_system_context("manager")
    assert "# SOUL" in out
    assert "main soul" in out
    assert "# ROLE_SYSTEM" in out
    assert "main role system" in out


def test_build_role_system_context_cache_invalidates_on_file_change(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_project_root(monkeypatch, tmp_path)
    ws = tmp_path / "runtime" / "workspaces" / "ops"
    ws.mkdir(parents=True, exist_ok=True)
    role_file = ws / "ROLE_SYSTEM.md"
    role_file.write_text("v1", encoding="utf-8")
    out1 = loader_mod.build_role_system_context("ops")
    assert "v1" in out1
    role_file.write_text("v2", encoding="utf-8")
    out2 = loader_mod.build_role_system_context("ops")
    assert "v2" in out2


def test_build_role_system_context_renders_template_vars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_project_root(monkeypatch, tmp_path)
    ws = tmp_path / "runtime" / "workspaces" / "ops"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "ROLE_SYSTEM.md").write_text("experts={{EXPERTS_HINT}}", encoding="utf-8")
    out = loader_mod.build_role_system_context("ops", template_vars={"EXPERTS_HINT": "ops,generalist"})
    assert "experts=ops,generalist" in out


def test_build_role_system_context_template_var_isolated_by_cache_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_project_root(monkeypatch, tmp_path)
    ws = tmp_path / "runtime" / "workspaces" / "ops"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "ROLE_SYSTEM.md").write_text("x={{A}}", encoding="utf-8")
    a = loader_mod.build_role_system_context("ops", template_vars={"A": "one"})
    b = loader_mod.build_role_system_context("ops", template_vars={"A": "two"})
    assert "x=one" in a
    assert "x=two" in b
