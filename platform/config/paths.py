"""仓库与数据文件路径解析（与框架无关，供 ``db`` / UI 等共用）。"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import time
import warnings
from pathlib import Path


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # Source layout: <repo>/platform/config/paths.py
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _project_root()
_DATA_MIGRATION_DONE = False


def _canonical_data_root() -> Path:
    return (PROJECT_ROOT / "data").resolve()


def _legacy_platform_data_root() -> Path:
    return (PROJECT_ROOT / "src" / "platform" / "data").resolve()


def _legacy_root_data_root() -> Path:
    return (PROJECT_ROOT.parent / "data").resolve()


def _backup_keep_count() -> int:
    raw = (os.getenv("AIA_ASSISTANT_PREMERGE_BACKUP_KEEP") or os.getenv("OPS_ASSISTANT_PREMERGE_BACKUP_KEEP") or "").strip()
    if not raw:
        return 3
    try:
        val = int(raw)
    except Exception:
        return 3
    return max(0, val)


def _cleanup_pre_merge_backups() -> None:
    root = _canonical_data_root()
    if not root.exists():
        return
    keep = _backup_keep_count()
    backups = sorted([p for p in root.glob("_pre_merge_sqlite_*") if p.is_dir()], key=lambda p: p.name, reverse=True)
    for old in backups[keep:]:
        try:
            shutil.rmtree(old)
        except Exception as exc:
            warnings.warn(f"自动清理旧备份失败（已跳过）: {old} ({exc})", RuntimeWarning, stacklevel=1)


def attachments_dir() -> Path:
    p = (_canonical_data_root() / "attachments").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _sqlite_sidecars(main: Path) -> list[Path]:
    return [main, Path(str(main) + "-wal"), Path(str(main) + "-shm")]


def _sqlite_chat_session_count(db: Path) -> int | None:
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=3.0)
        try:
            r = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='chat_session'").fetchone()
            if not r or int(r[0] or 0) == 0:
                return 0
            row = conn.execute("SELECT COUNT(*) FROM chat_session").fetchone()
            return int(row[0] or 0) if row else 0
        finally:
            conn.close()
    except Exception:
        return None


def _checkpoint_wal_best_effort(main: Path) -> None:
    try:
        conn = sqlite3.connect(str(main), timeout=5.0)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        finally:
            conn.close()
    except Exception:
        pass


def _copy_sqlite_bundle(src_main: Path, dst_main: Path) -> None:
    dst_main.parent.mkdir(parents=True, exist_ok=True)
    _checkpoint_wal_best_effort(src_main)
    for s in _sqlite_sidecars(src_main):
        if not s.exists():
            continue
        d = dst_main.parent / s.name
        if s.resolve() == d.resolve():
            continue
        shutil.copy2(s, d)


def _backup_sqlite_bundle_copy(main: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    _checkpoint_wal_best_effort(main)
    for s in _sqlite_sidecars(main):
        if s.exists():
            shutil.copy2(s, dest_dir / s.name)


def _merge_attachment_tree(src: Path, dst: Path) -> int:
    if not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in src.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(src)
        target = dst / rel
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        copied += 1
    return copied


def _run_default_data_migration(canonical_db: Path) -> None:
    legacy_root_data = _legacy_root_data_root()
    legacy_root_db = legacy_root_data / "ai_ops.sqlite"
    if legacy_root_db.exists() and not canonical_db.exists():
        _copy_sqlite_bundle(legacy_root_db, canonical_db)
    _merge_attachment_tree(legacy_root_data / "attachments", attachments_dir())

    legacy_platform_data = _legacy_platform_data_root()
    legacy_db = legacy_platform_data / "ai_ops.sqlite"
    if legacy_db.exists():
        leg_n = _sqlite_chat_session_count(legacy_db)
        if leg_n is not None:
            if not canonical_db.exists():
                _copy_sqlite_bundle(legacy_db, canonical_db)
            else:
                can_n = _sqlite_chat_session_count(canonical_db)
                can_n = 0 if can_n is None else can_n
                force = str(os.getenv("AIA_LEGACY_DB_FORCE_PREMERGE") or os.getenv("OPS_LEGACY_DB_FORCE_PREMERGE") or "").strip().lower() in (
                    "1",
                    "true",
                    "yes",
                    "on",
                )
                if force and leg_n > can_n:
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    bak = _canonical_data_root() / f"_pre_merge_sqlite_{ts}"
                    try:
                        _checkpoint_wal_best_effort(canonical_db)
                        _backup_sqlite_bundle_copy(canonical_db, bak)
                        _copy_sqlite_bundle(legacy_db, canonical_db)
                    except (OSError, PermissionError, shutil.Error) as exc:
                        warnings.warn(
                            "未能用旧库覆盖当前主库（可能被其它进程占用）。"
                            f"已备份当前库到: {bak}。可关闭占用后重启，或手动合并。原因: {exc}",
                            RuntimeWarning,
                            stacklevel=1,
                        )

    _merge_attachment_tree(legacy_platform_data / "attachments", attachments_dir())
    _cleanup_pre_merge_backups()


def db_path() -> str:
    global _DATA_MIGRATION_DONE
    p = os.getenv("AIA_ASSISTANT_DB_PATH") or os.getenv("OPS_ASSISTANT_DB_PATH") or "data/ai_ops.sqlite"
    path = Path(p)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    use_default = not (os.getenv("AIA_ASSISTANT_DB_PATH") or os.getenv("OPS_ASSISTANT_DB_PATH"))
    if use_default and not _DATA_MIGRATION_DONE:
        _DATA_MIGRATION_DONE = True
        try:
            _run_default_data_migration(path)
        except Exception as exc:
            warnings.warn(f"默认数据目录迁移未完全成功（可稍后重试或检查权限）: {exc}", RuntimeWarning, stacklevel=1)
    return str(path)


__all__ = ["PROJECT_ROOT", "attachments_dir", "db_path"]
