from __future__ import annotations

import os
from pathlib import Path

import pytest

from oclaw.platform.config import bootstrap_env as be


@pytest.fixture(autouse=True)
def _reset_bootstrap_flag():
    be._LOADED = False
    yield
    be._LOADED = False


def test_load_system_env_reads_only_local_system_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(be, "_project_root", lambda: tmp_path)
    loc = tmp_path / "_local"
    loc.mkdir(parents=True, exist_ok=True)
    (loc / "system.env").write_text("X=only_file\nY=z\n", encoding="utf-8")
    monkeypatch.delenv("X", raising=False)
    monkeypatch.delenv("Y", raising=False)

    loaded = be.load_system_env(force=True)
    assert len(loaded) == 1
    assert os.environ["X"] == "only_file"
    assert os.environ["Y"] == "z"


def test_load_system_env_does_not_override_process_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(be, "_project_root", lambda: tmp_path)
    loc = tmp_path / "_local"
    loc.mkdir(parents=True, exist_ok=True)
    (loc / "system.env").write_text("X=from_file\n", encoding="utf-8")
    monkeypatch.setenv("X", "from_shell")

    be.load_system_env(force=True)
    assert os.environ["X"] == "from_shell"


def test_load_system_env_missing_file_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(be, "_project_root", lambda: tmp_path)
    (tmp_path / "_local").mkdir(parents=True, exist_ok=True)

    loaded = be.load_system_env(force=True)
    assert loaded == []
