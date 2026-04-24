from __future__ import annotations

from pathlib import Path
import zipfile

from oclaw.runtime.skill_installer import (
    auto_install_skill_from_payload,
    create_skill_from_template,
    install_skill_from_local_dir,
    install_skill_from_registry_archive,
    list_skills_with_status,
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
    assert not (root / "roll_me_back").exists()


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

