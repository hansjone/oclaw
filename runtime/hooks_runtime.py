from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oclaw.runtime.skills import discover_workspace_skill_manifests
from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.platform.config.runtime_paths import runtime_hooks_bundled_root


@dataclass
class _HooksState:
    initialized: bool = False
    loaded_count: int = 0
    last_error: str = ""
    hooks_mod: Any = None
    resolved_config: dict[str, Any] | None = None


_STATE = _HooksState()


def _ensure_oclaw_path() -> Path:
    oclaw_dir = (Path(PROJECT_ROOT) / "oclaw").resolve()
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

    default_cfg_path = (Path(PROJECT_ROOT) / "oclaw" / "oclaw.json").resolve()
    file_cfg = _read_json_file(default_cfg_path)
    if isinstance(file_cfg, dict):
        cfg = _deep_merge_dict(cfg, file_cfg)
    return cfg


def initialize_hooks_runtime(*, cfg: dict[str, Any] | None, workspace_dir: str) -> int:
    if _STATE.initialized:
        return int(_STATE.loaded_count or 0)
    try:
        oclaw_dir = _ensure_oclaw_path()
        from oclaw.runtime import hooks as hooks_mod  # type: ignore

        bundled_dir = runtime_hooks_bundled_root()
        resolved_cfg = dict(cfg or resolve_runtime_config() or {})
        extra_dirs: list[str] = []
        try:
            for m in discover_workspace_skill_manifests():
                d = (Path(str(m.skill_dir or "")) / "hooks").resolve()
                if d.exists() and d.is_dir():
                    extra_dirs.append(str(d))
        except Exception:
            extra_dirs = []
        if extra_dirs:
            hooks_cfg = dict((resolved_cfg.get("hooks") or {})) if isinstance(resolved_cfg.get("hooks"), dict) else {}
            internal = dict((hooks_cfg.get("internal") or {})) if isinstance(hooks_cfg.get("internal"), dict) else {}
            load = dict((internal.get("load") or {})) if isinstance(internal.get("load"), dict) else {}
            prev = load.get("extraDirs")
            merged = []
            if isinstance(prev, list):
                merged.extend([str(x) for x in prev if str(x).strip()])
            merged.extend([x for x in extra_dirs if x and x not in set(merged)])
            load["extraDirs"] = merged
            internal["load"] = load
            hooks_cfg["internal"] = internal
            resolved_cfg["hooks"] = hooks_cfg
        loaded = int(
            hooks_mod.load_internal_hooks(
                resolved_cfg,
                workspace_dir=str(workspace_dir or "."),
                bundled_hooks_dir=str(bundled_dir),
            )
            or 0
        )
        _STATE.initialized = True
        _STATE.loaded_count = loaded
        _STATE.hooks_mod = hooks_mod
        _STATE.resolved_config = resolved_cfg
        _STATE.last_error = ""
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
        mutable_context = dict(context or {})
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
        return dict(context or {})


def get_active_hooks_config() -> dict[str, Any]:
    if isinstance(_STATE.resolved_config, dict):
        return dict(_STATE.resolved_config)
    return resolve_runtime_config()
