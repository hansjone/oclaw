"""Unit tests for workspace_profile_tool helpers and handler."""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.tools.path_guard import clear_workspace_path_access_for_tests, workspace_path_access_scope
from runtime.tools.public import workspace_profile_tool as mod


def test_walkable_dir_github_vs_vendor() -> None:
    assert mod._walkable_dir(".github") is True
    assert mod._walkable_dir(".gitlab") is True
    assert mod._walkable_dir("node_modules") is False
    assert mod._walkable_dir(".cache") is False


def test_path_suggests_ci() -> None:
    assert mod._path_suggests_ci(".github/workflows/ci.yml")
    assert mod._path_suggests_ci("pkg/.circleci/config.yml")
    assert mod._path_suggests_ci("bitbucket-pipelines.yml")
    assert mod._path_suggests_ci("ci/Jenkinsfile")
    assert mod._path_suggests_ci(str(Path("x") / ".woodpecker" / "ci.yaml"))
    assert not mod._path_suggests_ci("src/main.py")


def test_looks_like_test_file() -> None:
    assert mod._looks_like_test_file("tests/unit/test_x.py")
    assert mod._looks_like_test_file(str(Path("src") / "tests" / "a.py"))
    assert mod._looks_like_test_file("test_foo.py")
    assert not mod._looks_like_test_file("src/main.py")


def test_detect_package_manager_nuget_csproj() -> None:
    files = [
        {"path": "src/App.csproj", "size": 12, "ext": ".csproj", "suffix": ".csproj"},
    ]
    out = mod._detect_package_manager(files)
    assert out["detected"] is True
    assert "nuget" in out["managers"]
    assert "App.csproj" in out["config_files"]


def test_workspace_profile_max_files_clamped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    clear_workspace_path_access_for_tests()
    spec = mod.workspace_profile_tool()
    with workspace_path_access_scope(None, None):
        r = spec.handler({"root": ".", "max_files": 0})
    assert r.get("ok") is True
    assert (r.get("profile") or {}).get("total_files_scanned") == 1

    with workspace_path_access_scope(None, None):
        r2 = spec.handler({"root": ".", "max_files": 999_999})
    assert r2.get("ok") is True
    assert (r2.get("profile") or {}).get("truncated") is False
