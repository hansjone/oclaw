"""Regression: default DB migration must not overwrite canonical DB when session count drops after deletes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import svc.config.paths as paths_mod


def _legacy_dir(tmp_path: Path) -> Path:
    d = tmp_path / "src" / "platform" / "data"
    d.mkdir(parents=True)
    return d


def test_no_overwrite_when_legacy_has_more_sessions_than_canonical(tmp_path, monkeypatch) -> None:
    """Previously leg_n > can_n triggered a full replace — wrong after user deletes sessions."""
    leg_root = _legacy_dir(tmp_path)
    monkeypatch.setattr(paths_mod, "PROJECT_ROOT", tmp_path)
    canonical = tmp_path / "oclaw" / "data" / "ai_ops.sqlite"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("current_db", encoding="utf-8")
    legacy = leg_root / "ai_ops.sqlite"
    legacy.write_text("stale_db", encoding="utf-8")
    monkeypatch.delenv("OPS_LEGACY_DB_FORCE_PREMERGE", raising=False)

    with patch.object(paths_mod, "_copy_sqlite_bundle") as cp:
        with patch.object(paths_mod, "_sqlite_chat_session_count", side_effect=[50, 2]):
            paths_mod._run_default_data_migration(canonical.resolve())
    cp.assert_not_called()
    assert canonical.read_text(encoding="utf-8") == "current_db"


def test_force_premerege_still_overwrites_when_opt_in(tmp_path, monkeypatch) -> None:
    leg_root = _legacy_dir(tmp_path)
    monkeypatch.setattr(paths_mod, "PROJECT_ROOT", tmp_path)
    canonical = tmp_path / "oclaw" / "data" / "ai_ops.sqlite"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("current_db", encoding="utf-8")
    legacy = leg_root / "ai_ops.sqlite"
    legacy.write_text("stale_db", encoding="utf-8")
    monkeypatch.setenv("OPS_LEGACY_DB_FORCE_PREMERGE", "1")

    with patch.object(paths_mod, "_backup_sqlite_bundle_copy"):
        with patch.object(paths_mod, "_checkpoint_wal_best_effort"):
            with patch.object(paths_mod, "_copy_sqlite_bundle") as cp:
                with patch.object(paths_mod, "_sqlite_chat_session_count", side_effect=[50, 2]):
                    paths_mod._run_default_data_migration(canonical.resolve())
    cp.assert_called_once()


def test_seed_from_legacy_when_canonical_missing(tmp_path, monkeypatch) -> None:
    leg_root = _legacy_dir(tmp_path)
    monkeypatch.setattr(paths_mod, "PROJECT_ROOT", tmp_path)
    canonical = tmp_path / "oclaw" / "data" / "ai_ops.sqlite"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    assert not canonical.exists()
    legacy = leg_root / "ai_ops.sqlite"
    legacy.write_text("from_legacy", encoding="utf-8")

    with patch.object(paths_mod, "_sqlite_chat_session_count", return_value=3):
        with patch.object(paths_mod, "_merge_attachment_tree"):
            with patch.object(paths_mod, "_cleanup_pre_merge_backups"):
                paths_mod._run_default_data_migration(canonical.resolve())
    assert canonical.read_text(encoding="utf-8") == "from_legacy"
