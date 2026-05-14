"""Central logging setup: rotating files under :func:`svc.config.log_paths.oclaw_log_root`."""

from __future__ import annotations

import logging.config
import os
from pathlib import Path
from typing import Any

from svc.config.log_paths import oclaw_log_root

_CONFIGURED = False


def _skip_file_handlers() -> bool:
    if str(os.getenv("AIA_LOG_TO_FILE") or "").strip().lower() in ("0", "false", "no", "off"):
        return True
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return False


def skip_file_logging() -> bool:
    """Whether rotating file handlers are disabled (pytest or ``AIA_LOG_TO_FILE=0``)."""
    return _skip_file_handlers()


def _resolve_level_name() -> str:
    raw = (os.environ.get("OCLAW_LOG_LEVEL") or os.environ.get("AIA_LOG_LEVEL") or "INFO").strip().upper()
    if raw not in ("DEBUG", "INFO", "WARNING", "WARN", "ERROR", "CRITICAL", "FATAL"):
        return "INFO"
    if raw == "WARN":
        return "WARNING"
    if raw == "FATAL":
        return "CRITICAL"
    return raw


def _int_env(name: str, default: int) -> int:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def build_worker_logging_dict_config(
    *,
    log_root: Path | None = None,
    level: str | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> dict[str, Any]:
    """dictConfig for non-uvicorn workers (plain :mod:`logging` formatters)."""
    root = log_root or oclaw_log_root()
    lvl = level or _resolve_level_name()
    mb = int(max_bytes if max_bytes is not None else _int_env("OCLAW_LOG_MAX_BYTES", 20_971_520))
    bc = int(backup_count if backup_count is not None else _int_env("OCLAW_LOG_BACKUP_COUNT", 5))
    app_dir = root / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    oclaw_path = app_dir / "oclaw.log"
    fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "file": {
                "format": fmt,
                "datefmt": datefmt,
            },
        },
        "handlers": {
            "oclaw_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "file",
                "filename": str(oclaw_path),
                "maxBytes": max(256_000, mb),
                "backupCount": max(0, min(bc, 100)),
                "encoding": "utf-8",
            },
        },
        "root": {"handlers": ["oclaw_file"], "level": lvl},
    }


def build_uvicorn_logging_dict_config(
    *,
    log_root: Path | None = None,
    level: str | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> dict[str, Any]:
    """dictConfig compatible with ``uvicorn.run(log_config=...)`` (uses uvicorn formatters)."""
    root = log_root or oclaw_log_root()
    lvl = level or _resolve_level_name()
    mb = int(max_bytes if max_bytes is not None else _int_env("OCLAW_LOG_MAX_BYTES", 20_971_520))
    bc = int(backup_count if backup_count is not None else _int_env("OCLAW_LOG_BACKUP_COUNT", 5))
    app_dir = root / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    oclaw_path = app_dir / "oclaw.log"
    access_path = app_dir / "uvicorn-access.log"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": False,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            },
        },
        "handlers": {
            "default_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "default",
                "filename": str(oclaw_path),
                "maxBytes": max(256_000, mb),
                "backupCount": max(0, min(bc, 100)),
                "encoding": "utf-8",
            },
            "access_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "access",
                "filename": str(access_path),
                "maxBytes": max(256_000, mb),
                "backupCount": max(0, min(bc, 100)),
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default_file"], "level": lvl, "propagate": False},
            "uvicorn.error": {"handlers": ["default_file"], "level": lvl, "propagate": False},
            "uvicorn.access": {"handlers": ["access_file"], "level": lvl, "propagate": False},
        },
        "root": {"handlers": ["default_file"], "level": lvl},
    }


def configure_oclaw_logging(
    *,
    service_name: str | None = None,
    include_uvicorn_formatters: bool = False,
    _force_file_handlers: bool = False,
) -> None:
    """Prepare or apply rotating file logging under the runtime log root (idempotent).

    Skips file handlers during pytest (``PYTEST_CURRENT_TEST``) or when
    ``AIA_LOG_TO_FILE=0`` (false/no/off), unless ``_force_file_handlers`` is true (tests only).

    When ``include_uvicorn_formatters`` is true, only creates ``log_root`` / ``app``; the caller
    must pass :func:`build_uvicorn_logging_dict_config` to ``uvicorn.run(log_config=...)`` so
    ``dictConfig`` runs once (avoids duplicate handlers).

    ``service_name`` is reserved for future structured fields; process/service is still visible
    in logger names and file layout (``app/oclaw.log`` per process).
    """
    global _CONFIGURED
    _ = service_name
    if _CONFIGURED:
        return
    if _skip_file_handlers() and not _force_file_handlers:
        _CONFIGURED = True
        return
    log_root = oclaw_log_root()
    log_root.mkdir(parents=True, exist_ok=True)
    (log_root / "app").mkdir(parents=True, exist_ok=True)
    if include_uvicorn_formatters:
        _CONFIGURED = True
        return
    logging.config.dictConfig(build_worker_logging_dict_config(log_root=log_root))
    _CONFIGURED = True


def reset_oclaw_logging_for_tests() -> None:
    """Clear idempotency flag (tests only)."""
    global _CONFIGURED
    _CONFIGURED = False


__all__ = [
    "build_uvicorn_logging_dict_config",
    "build_worker_logging_dict_config",
    "configure_oclaw_logging",
    "reset_oclaw_logging_for_tests",
    "skip_file_logging",
]
