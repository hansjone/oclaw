from __future__ import annotations

from pathlib import Path
import zipfile
import subprocess

from oclaw.runtime.skill_installer import (
    auto_install_skill_from_payload,
    create_skill_from_template,
    install_skill_from_local_dir,
    install_skill_from_registry_archive,
    list_skills_with_status,
    repair_skill_dependencies,
    set_skill_enabled,
)
from oclaw.platform.persistence.sqlite_store import SqliteStore


def test_create_list_and_disable_skill(tmp_path: Path) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    out = create_skill_from_template(
        store=store,
        name="demo_skill",
        description="demo",
        body_markdown="hello",
        skills_root=tmp_path / "skills",
    )
    assert out.ok
    rows = list_skills_with_status(store=store, skills_root=tmp_path / "skills")
    assert len(rows) == 1
    assert rows[0]["name"] == "demo_skill"
    assert rows[0]["enabled"] is True
    set_skill_enabled(store=store, skill_name="demo_skill", enabled=False)
    rows2 = list_skills_with_status(store=store, skills_root=tmp_path / "skills")
    assert rows2[0]["enabled"] is False


def test_auto_install_rollback_on_forced_error(tmp_path: Path) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    root = tmp_path / "skills"
    out = auto_install_skill_from_payload(
        store=store,
        payload={
            "name": "roll_me_back",
            "description": "demo",
            "body_markdown": "x",
            "force_error_for_test": True,
        },
        skills_root=root,
    )
    assert out.ok is False
    assert out.retryable is True
    assert out.error_code == "runtime_error"
    assert not (root / "_workspace" / "roll_me_back").exists()


def test_auto_install_enables_binding_for_all_roles(tmp_path: Path) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    root = tmp_path / "skills"
    out = auto_install_skill_from_payload(
        store=store,
        payload={
            "name": "auto_bound_skill",
            "description": "demo",
            "body_markdown": "x",
        },
        skills_root=root,
    )
    assert out.ok is True
    assert out.auto_enabled is True
    assert len(out.binding_applied_roles) >= 1
    assert (root / "_workspace" / "auto_bound_skill" / "SKILL.md").exists()
    mapping_raw = str(store.get_setting("skill_role_binding") or "").strip()
    assert mapping_raw
    import json

    mapping = json.loads(mapping_raw)
    assert isinstance(mapping, dict)
    assert any("auto_bound_skill" in (mapping.get(k) or []) for k in mapping.keys())


def test_install_skill_from_registry_archive_file_url(tmp_path: Path) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    pkg_dir = tmp_path / "pkg"
    inner = pkg_dir / "demo"
    inner.mkdir(parents=True, exist_ok=True)
    (inner / "SKILL.md").write_text(
        "---\nname: reg_demo\ndescription: x\nmetadata: {\"oclaw\":{}}\n---\n",
        encoding="utf-8",
    )
    archive = tmp_path / "reg.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(inner / "SKILL.md", arcname="demo/SKILL.md")
    out = install_skill_from_registry_archive(
        store=store,
        archive_url=archive.resolve().as_uri(),
        skills_root=tmp_path / "skills",
    )
    assert out.ok
    assert out.name == "reg_demo"


def test_install_skill_from_registry_archive_workspace_auto_bind(tmp_path: Path) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    pkg_dir = tmp_path / "pkg_ws"
    inner = pkg_dir / "demo"
    inner.mkdir(parents=True, exist_ok=True)
    (inner / "SKILL.md").write_text(
        "---\nname: reg_ws_demo\ndescription: x\nmetadata: {\"oclaw\":{}}\n---\n",
        encoding="utf-8",
    )
    archive = tmp_path / "reg_ws.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(inner / "SKILL.md", arcname="demo/SKILL.md")
    root = tmp_path / "skills"
    out = install_skill_from_registry_archive(
        store=store,
        archive_url=archive.resolve().as_uri(),
        skills_root=root / "_workspace",
        auto_bind=True,
    )
    assert out.ok
    assert out.name == "reg_ws_demo"
    assert out.auto_enabled is True
    assert len(out.binding_applied_roles) >= 1
    assert (root / "_workspace" / "reg_ws_demo" / "SKILL.md").exists()


def test_install_skill_from_clawhub_page_url(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    pkg_dir = tmp_path / "pkg_clawhub"
    inner = pkg_dir / "demo"
    inner.mkdir(parents=True, exist_ok=True)
    (inner / "SKILL.md").write_text(
        "---\nname: reg_clawhub_demo\ndescription: x\nmetadata: {\"oclaw\":{}}\n---\n",
        encoding="utf-8",
    )
    archive = tmp_path / "reg_clawhub.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(inner / "SKILL.md", arcname="demo/SKILL.md")

    captured: dict[str, str] = {}

    def _mock_get_detail(slug: str, *, cfg=None):  # noqa: ANN001,ARG001
        captured["slug"] = slug
        return {"archiveUrl": archive.resolve().as_uri()}

    monkeypatch.setattr("oclaw.runtime.tools.skills.clawhub_client.get_skill_detail", _mock_get_detail)

    out = install_skill_from_registry_archive(
        store=store,
        archive_url="https://clawhub.ai/pskoett/self-improving-agent",
        skills_root=tmp_path / "skills",
    )
    assert captured["slug"] == "self-improving-agent"
    assert out.ok
    assert out.name == "reg_clawhub_demo"


def test_install_local_allows_sh_files(tmp_path: Path) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    src = tmp_path / "local_skill"
    src.mkdir(parents=True, exist_ok=True)
    (src / "SKILL.md").write_text(
        "---\nname: local_with_sh\ndescription: x\nmetadata: {\"oclaw\":{}}\n---\n",
        encoding="utf-8",
    )
    (src / "activator.sh").write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")

    out = install_skill_from_local_dir(store=store, source_dir=src, skills_root=tmp_path / "skills")
    assert out.ok
    assert out.name == "local_with_sh"


def test_install_local_auto_installs_python_requirements(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    src = tmp_path / "skill_with_reqs"
    src.mkdir(parents=True, exist_ok=True)
    (src / "SKILL.md").write_text(
        "---\nname: with_reqs\ndescription: x\nmetadata: {\"oclaw\":{}}\n---\n",
        encoding="utf-8",
    )
    (src / "requirements.txt").write_text("requests>=2.0.0\n", encoding="utf-8")

    calls: list[list[str]] = []

    def _mock_run(cmd, **kwargs):  # noqa: ANN001
        calls.append([str(x) for x in cmd])
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("oclaw.runtime.skill_installer.subprocess.run", _mock_run)
    out = install_skill_from_local_dir(store=store, source_dir=src, skills_root=tmp_path / "skills")
    assert out.ok
    assert any(("pip" in " ".join(c) and "-r" in c) for c in calls)


def test_install_local_dependency_install_failure_returns_warning(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    src = tmp_path / "skill_with_bad_reqs"
    src.mkdir(parents=True, exist_ok=True)
    (src / "SKILL.md").write_text(
        "---\nname: with_bad_reqs\ndescription: x\nmetadata: {\"oclaw\":{}}\n---\n",
        encoding="utf-8",
    )
    (src / "requirements.txt").write_text("not_a_real_pkg_zzz\n", encoding="utf-8")

    def _mock_run(cmd, **kwargs):  # noqa: ANN001,ARG001
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="install failed")

    monkeypatch.setattr("oclaw.runtime.skill_installer.subprocess.run", _mock_run)
    out = install_skill_from_local_dir(store=store, source_dir=src, skills_root=tmp_path / "skills")
    assert out.ok
    assert out.detail.startswith("installed_with_dependency_warnings:")


def test_install_local_probe_missing_imports_and_install(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    src = tmp_path / "skill_probe_imports"
    src.mkdir(parents=True, exist_ok=True)
    (src / "SKILL.md").write_text(
        "---\nname: probe_imports\ndescription: x\nmetadata: {\"oclaw\":{}}\n---\n",
        encoding="utf-8",
    )
    (src / "main.py").write_text(
        "import json\nimport office\nimport pandas\nimport totally_missing_pkg_xyz\n",
        encoding="utf-8",
    )
    office_dir = src / "office"
    office_dir.mkdir(parents=True, exist_ok=True)
    (office_dir / "__init__.py").write_text("", encoding="utf-8")

    calls: list[list[str]] = []

    def _mock_run(cmd, **kwargs):  # noqa: ANN001,ARG001
        calls.append([str(x) for x in cmd])
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("oclaw.runtime.skill_installer.subprocess.run", _mock_run)
    out = install_skill_from_local_dir(store=store, source_dir=src, skills_root=tmp_path / "skills")
    assert out.ok
    pip_calls = [c for c in calls if ("pip" in " ".join(c))]
    assert pip_calls
    assert any("totally_missing_pkg_xyz" in c for c in pip_calls)


def test_repair_skill_dependencies_for_installed_skill(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    src = tmp_path / "skill_repair"
    src.mkdir(parents=True, exist_ok=True)
    (src / "SKILL.md").write_text(
        "---\nname: skill_repair\ndescription: x\nmetadata: {\"oclaw\":{}}\n---\n",
        encoding="utf-8",
    )
    (src / "main.py").write_text("import definitely_missing_pkg_abc\n", encoding="utf-8")

    calls: list[list[str]] = []

    def _mock_run(cmd, **kwargs):  # noqa: ANN001,ARG001
        calls.append([str(x) for x in cmd])
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("oclaw.runtime.skill_installer.subprocess.run", _mock_run)
    out = install_skill_from_local_dir(store=store, source_dir=src, skills_root=tmp_path / "skills")
    assert out.ok
    calls.clear()
    result = repair_skill_dependencies(store=store, skill_name="skill_repair", skills_root=tmp_path / "skills")
    assert bool(result.get("ok")) is True
    assert any("definitely_missing_pkg_abc" in c for c in calls)

