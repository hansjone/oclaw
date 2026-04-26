from __future__ import annotations

from pathlib import Path

import pytest

from oclaw.runtime.workspaces import experts as experts_mod
from oclaw.runtime.agents.specialists import discover_specialist_ids


def _set_project_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(experts_mod, "PROJECT_ROOT", tmp_path)


def test_list_experts_reads_runtime_workspaces(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_project_root(monkeypatch, tmp_path)
    ws = tmp_path / "oclaw" / "runtime" / "workspaces" / "qa"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "SOUL.md").write_text("qa soul", encoding="utf-8")
    rows = experts_mod.list_experts()
    ids = {str(x.get("id") or "") for x in rows}
    assert "qa" in ids


def test_create_expert_requires_soul(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_project_root(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="soul_required"):
        experts_mod.create_expert(expert_id="qa", files={})


def test_create_expert_rejects_legacy_file_names(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_project_root(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="unsupported_file_name"):
        experts_mod.create_expert(expert_id="qa", files={"SOUL.md": "ok", "AGENTS.md": "legacy"})


def test_create_update_delete_expert_flow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_project_root(monkeypatch, tmp_path)
    created = experts_mod.create_expert(
        expert_id="qa",
        files={"SOUL.md": "init soul", "ROLE_SYSTEM.md": "role system"},
    )
    assert created["id"] == "qa"
    experts_mod.update_expert_files(expert_id="qa", files={"SOUL.md": "updated soul"})
    rows = experts_mod.list_experts()
    qa = next((x for x in rows if str(x.get("id") or "") == "qa"), {})
    files = qa.get("files") if isinstance(qa, dict) else {}
    assert "updated soul" in str((files or {}).get("SOUL.md") or "")
    experts_mod.delete_expert("qa")
    rows2 = experts_mod.list_experts()
    assert all(str(x.get("id") or "") != "qa" for x in rows2)


def test_delete_builtin_expert_is_protected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_project_root(monkeypatch, tmp_path)
    ws = tmp_path / "oclaw" / "runtime" / "workspaces" / "main"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "SOUL.md").write_text("main soul", encoding="utf-8")
    with pytest.raises(ValueError, match="builtin_expert_protected"):
        experts_mod.delete_expert("main")


def test_discover_specialists_reads_workspaces(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_project_root(monkeypatch, tmp_path)
    ws = tmp_path / "oclaw" / "runtime" / "workspaces"
    (ws / "main").mkdir(parents=True, exist_ok=True)
    (ws / "generalist").mkdir(parents=True, exist_ok=True)
    (ws / "generalist" / "ROLE_SYSTEM.md").write_text("g", encoding="utf-8")
    (ws / "ops").mkdir(parents=True, exist_ok=True)
    (ws / "ops" / "ROLE_SYSTEM.md").write_text("o", encoding="utf-8")
    (ws / "qa").mkdir(parents=True, exist_ok=True)
    (ws / "qa" / "SOUL.md").write_text("q", encoding="utf-8")
    got = set(discover_specialist_ids())
    assert "qa" in got
    assert "main" not in got


def test_build_expert_catalog_block_contains_dynamic_experts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_project_root(monkeypatch, tmp_path)
    ws = tmp_path / "oclaw" / "runtime" / "workspaces"
    (ws / "main").mkdir(parents=True, exist_ok=True)
    (ws / "qa").mkdir(parents=True, exist_ok=True)
    (ws / "qa" / "SOUL.md").write_text("QA expert soul", encoding="utf-8")
    (ws / "qa" / "ROLE_SYSTEM.md").write_text("Handle test plans and regressions", encoding="utf-8")
    block = experts_mod.build_expert_catalog_block(include_main=False, per_field_limit=80, max_total_chars=500)
    assert "qa" in block
    assert "role_system=" in block
    assert "soul=" in block


def test_discover_specialists_cache_invalidates_after_create(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_project_root(monkeypatch, tmp_path)
    ws = tmp_path / "oclaw" / "runtime" / "workspaces"
    (ws / "main").mkdir(parents=True, exist_ok=True)
    (ws / "generalist").mkdir(parents=True, exist_ok=True)
    (ws / "generalist" / "SOUL.md").write_text("g", encoding="utf-8")
    before = set(discover_specialist_ids())
    assert "qa" not in before
    experts_mod.create_expert(expert_id="qa", files={"SOUL.md": "qa soul"})
    after = set(discover_specialist_ids())
    assert "qa" in after
