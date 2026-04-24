from __future__ import annotations

from pathlib import Path

import oclaw.platform.config.paths as paths_mod


def _mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)
    (p / "marker.txt").write_text("x", encoding="utf-8")


def test_pre_merge_backup_retention_default_keep_3(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "oclaw" / "data"
    for ts in ("20260101_000001", "20260101_000002", "20260101_000003", "20260101_000004", "20260101_000005"):
        _mkdir(data_dir / f"_pre_merge_sqlite_{ts}")
    monkeypatch.setenv("OPS_ASSISTANT_PREMERGE_BACKUP_KEEP", "")
    monkeypatch.setattr(paths_mod, "PROJECT_ROOT", tmp_path)
    paths_mod._cleanup_pre_merge_backups()

    keep = sorted(p.name for p in data_dir.glob("_pre_merge_sqlite_*") if p.is_dir())
    assert keep == [
        "_pre_merge_sqlite_20260101_000003",
        "_pre_merge_sqlite_20260101_000004",
        "_pre_merge_sqlite_20260101_000005",
    ]


def test_pre_merge_backup_retention_respects_env_keep(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "oclaw" / "data"
    for ts in ("20260101_000001", "20260101_000002", "20260101_000003"):
        _mkdir(data_dir / f"_pre_merge_sqlite_{ts}")
    monkeypatch.setenv("OPS_ASSISTANT_PREMERGE_BACKUP_KEEP", "1")
    monkeypatch.setattr(paths_mod, "PROJECT_ROOT", tmp_path)
    paths_mod._cleanup_pre_merge_backups()

    keep = sorted(p.name for p in data_dir.glob("_pre_merge_sqlite_*") if p.is_dir())
    assert keep == ["_pre_merge_sqlite_20260101_000003"]
