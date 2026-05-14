"""Tests for :mod:`svc.observability.logging_setup` and :mod:`svc.config.log_paths`."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from svc.config import log_paths
from svc.observability import logging_setup


def test_oclaw_log_root_respects_aia_runtime_log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIA_RUNTIME_LOG_DIR", str(tmp_path / "xlogs"))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert log_paths.oclaw_log_root() == (tmp_path / "xlogs").resolve()


def test_configure_worker_writes_rotating_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_root = tmp_path / "logs"
    monkeypatch.setenv("AIA_RUNTIME_LOG_DIR", str(log_root))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    logging_setup.reset_oclaw_logging_for_tests()

    logging_setup.configure_oclaw_logging(
        service_name="test",
        include_uvicorn_formatters=False,
        _force_file_handlers=True,
    )
    log = logging.getLogger("test_logging_module")
    log.warning("hello from logging setup test")

    app_log = log_root / "app" / "oclaw.log"
    assert app_log.is_file()
    text = app_log.read_text(encoding="utf-8", errors="replace")
    assert "hello from logging setup test" in text

    logging_setup.configure_oclaw_logging(
        service_name="test",
        include_uvicorn_formatters=False,
        _force_file_handlers=True,
    )
    handlers = [h for h in logging.root.handlers if hasattr(h, "baseFilename")]
    assert len(handlers) == 1


def test_configure_uvicorn_deferred_marks_configured_without_dictconfig(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_root = tmp_path / "logs2"
    monkeypatch.setenv("AIA_RUNTIME_LOG_DIR", str(log_root))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    logging_setup.reset_oclaw_logging_for_tests()

    logging_setup.configure_oclaw_logging(
        service_name="gw",
        include_uvicorn_formatters=True,
        _force_file_handlers=True,
    )
    assert (log_root / "app").is_dir()
    assert not (log_root / "app" / "oclaw.log").exists()


def test_oclaw_hooks_log_dir_defaults_under_runtime_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIA_RUNTIME_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.delenv("OCLAW_HOOK_LOG_USE_STATE_DIR", raising=False)
    state = tmp_path / "fake_state"
    state.mkdir()
    d = log_paths.oclaw_hooks_log_dir(state_dir_if_legacy=state)
    assert d == (tmp_path / "logs" / "hooks").resolve()
    assert d.is_dir()


def test_oclaw_hooks_log_dir_legacy_when_env_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIA_RUNTIME_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("OCLAW_HOOK_LOG_USE_STATE_DIR", "1")
    state = tmp_path / "fake_state"
    state.mkdir()
    d = log_paths.oclaw_hooks_log_dir(state_dir_if_legacy=state)
    assert d == (state / "logs").resolve()
