from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.hooks.hook_types import HookEligibilityContext
from runtime.hooks.merge_skill_hook_dirs import merge_skill_hook_extra_dirs_into_config
from svc.config.paths import PROJECT_ROOT
from svc.config.runtime_paths import runtime_hooks_bundled_root


@dataclass
class _HooksState:
    initialized: bool = False
    loaded_count: int = 0
    last_error: str = ""
    hooks_mod: Any = None
    resolved_config: dict[str, Any] | None = None


_STATE = _HooksState()
_log_gmail = logging.getLogger("oclaw.hooks.gmail")


class _GmailWatcherLogAdapter:
    def info(self, msg: str) -> None:
        _log_gmail.info("%s", msg)

    def warn(self, msg: str) -> None:
        _log_gmail.warning("%s", msg)

    def error(self, msg: str) -> None:
        _log_gmail.error("%s", msg)


def _maybe_start_gmail_watcher_with_logs(resolved_cfg: dict[str, Any]) -> None:
    """After hooks load: parity hook for OpenClaw gateway post-attach Gmail lifecycle."""
    try:
        from runtime.hooks.gmail_watcher_lifecycle import start_gmail_watcher_with_logs

        start_gmail_watcher_with_logs(cfg=resolved_cfg, log=_GmailWatcherLogAdapter())
    except Exception:
        _log_gmail.exception("gmail watcher lifecycle failed")


def _reset_hooks_runtime_state_for_test() -> None:
    _STATE.initialized = False
    _STATE.loaded_count = 0
    _STATE.last_error = ""
    _STATE.hooks_mod = None
    _STATE.resolved_config = None


def _ensure_oclaw_path() -> Path:
    oclaw_dir = Path(PROJECT_ROOT).resolve()
    if str(oclaw_dir) not in sys.path:
        sys.path.insert(0, str(oclaw_dir))
    return oclaw_dir


def _default_runtime_config() -> dict[str, Any]:
    return {"hooks": {"internal": {"enabled": True}}}


def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = dict(base)
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_dict(dict(out.get(k) or {}), v)
        else:
            out[k] = v
    return out


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists() or not path.is_file():
            return None
        raw = path.read_text(encoding="utf-8")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def resolve_runtime_config() -> dict[str, Any]:
    cfg = _default_runtime_config()
    env_json = str(os.getenv("OCLAW_RUNTIME_CONFIG_JSON") or "").strip()
    if env_json:
        try:
            obj = json.loads(env_json)
            if isinstance(obj, dict):
                cfg = _deep_merge_dict(cfg, obj)
                return cfg
        except Exception:
            pass

    raw_path = str(os.getenv("OCLAW_CONFIG_PATH") or "").strip()
    if raw_path:
        p = Path(raw_path).expanduser()
        if not p.is_absolute():
            p = (Path(PROJECT_ROOT) / p).resolve()
        file_cfg = _read_json_file(p)
        if isinstance(file_cfg, dict):
            cfg = _deep_merge_dict(cfg, file_cfg)
            return cfg

    default_cfg_path = (Path(PROJECT_ROOT) / "oclaw.json").resolve()
    file_cfg = _read_json_file(default_cfg_path)
    if isinstance(file_cfg, dict):
        cfg = _deep_merge_dict(cfg, file_cfg)
    return cfg


def initialize_hooks_runtime(
    *,
    cfg: dict[str, Any] | None,
    workspace_dir: str,
    eligibility: HookEligibilityContext | None = None,
) -> int:
    if _STATE.initialized:
        return int(_STATE.loaded_count or 0)
    try:
        oclaw_dir = _ensure_oclaw_path()
        from runtime import hooks as hooks_mod  # type: ignore

        bundled_dir = runtime_hooks_bundled_root()
        resolved_cfg = merge_skill_hook_extra_dirs_into_config(dict(cfg or resolve_runtime_config() or {}))
        loaded = int(
            hooks_mod.load_internal_hooks(
                resolved_cfg,
                workspace_dir=str(workspace_dir or "."),
                bundled_hooks_dir=str(bundled_dir),
                eligibility=eligibility,
            )
            or 0
        )
        _STATE.initialized = True
        _STATE.loaded_count = loaded
        _STATE.hooks_mod = hooks_mod
        _STATE.resolved_config = resolved_cfg
        _STATE.last_error = ""
        _maybe_start_gmail_watcher_with_logs(resolved_cfg)
        return loaded
    except Exception as exc:
        _STATE.initialized = True
        _STATE.loaded_count = 0
        _STATE.hooks_mod = None
        _STATE.resolved_config = None
        _STATE.last_error = f"{type(exc).__name__}: {exc}"
        return 0


def hooks_status() -> dict[str, Any]:
    return {
        "initialized": bool(_STATE.initialized),
        "loaded_count": int(_STATE.loaded_count or 0),
        "last_error": str(_STATE.last_error or ""),
        "has_config": isinstance(_STATE.resolved_config, dict),
    }


def _trigger_async_or_sync(coro: Any) -> None:
    if not asyncio.iscoroutine(coro):
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        loop.create_task(coro)
    else:
        asyncio.run(coro)


def trigger_hook_event(
    *,
    event_type: str,
    action: str,
    session_key: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hooks_mod = _STATE.hooks_mod
    if hooks_mod is None:
        return {}
    try:
        mutable_context: dict[str, Any] = {} if context is None else context
        ev = hooks_mod.create_hook_event(
            str(event_type or ""),
            str(action or ""),
            str(session_key or "system"),
            context=mutable_context,
        )
        _trigger_async_or_sync(hooks_mod.trigger_hook(ev))
        if isinstance(getattr(ev, "context", None), dict):
            return dict(getattr(ev, "context"))
        return mutable_context
    except Exception:
        return dict(context) if context is not None else {}


def get_active_hooks_config() -> dict[str, Any]:
    if isinstance(_STATE.resolved_config, dict):
        return dict(_STATE.resolved_config)
    return resolve_runtime_config()
