from __future__ import annotations

import os
import platform
import shutil
from typing import Any, Dict, Optional

from .hook_manifest_core import HookMetadataSpec, HookRequiresSpec
from .hook_types import HookEligibilityContext, HookEntry, ensure_hook_entry
from .policy import resolve_hook_config, resolve_hook_enable_state

_DEFAULT_CONFIG_VALUES: Dict[str, bool] = {
    "browser.enabled": True,
    "browser.evaluateEnabled": True,
    "workspace.dir": True,
}


def _resolve_config_path(config: Optional[Dict[str, Any]], path_str: str) -> Any:
    if not isinstance(config, dict):
        return None
    cur: Any = config
    for segment in str(path_str or "").split("."):
        key = segment.strip()
        if not key:
            continue
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _is_config_path_truthy(config: Optional[Dict[str, Any]], path_str: str) -> bool:
    key = str(path_str or "").strip()
    if not key:
        return False
    value = _resolve_config_path(config, key)
    if value is None and key in _DEFAULT_CONFIG_VALUES:
        return _DEFAULT_CONFIG_VALUES[key]
    return bool(value)


def _has_binary(bin_name: str) -> bool:
    return bool(shutil.which(str(bin_name or "").strip()))


def _resolve_runtime_platform() -> str:
    return str(platform.system() or "").strip().lower()


def _normalize_os_name(os_name: str) -> str:
    v = str(os_name or "").strip().lower()
    if v in {"mac", "macos", "darwin"}:
        return "darwin"
    if v in {"win", "windows"}:
        return "windows"
    if v in {"linux"}:
        return "linux"
    return v


def _hook_os_gate_satisfied(*, hook_os: tuple[str, ...], remote_platforms: list[str]) -> bool:
    """
    Match OpenClaw ``evaluateRuntimeEligibility`` OS rule:

    If the hook declares ``os``, pass when the **local** runtime matches *or* when any
    advertised **remote** platform matches one of the hook's supported OS names.
    """
    os_list = [str(x).strip() for x in hook_os if str(x or "").strip()]
    if not os_list:
        return True
    cur = _normalize_os_name(_resolve_runtime_platform())
    hook_names = {_normalize_os_name(x) for x in os_list}
    if cur in hook_names:
        return True
    rem = [_normalize_os_name(x) for x in remote_platforms if str(x or "").strip()]
    return any(r in hook_names for r in rem)


def _parse_requires_obj(raw: Any) -> HookRequiresSpec:
    row = raw if isinstance(raw, dict) else {}
    bins = tuple(str(x).strip() for x in list(row.get("bins") or []) if str(x).strip())
    any_bins = tuple(str(x).strip() for x in list(row.get("anyBins") or []) if str(x).strip())
    env = tuple(str(x).strip() for x in list(row.get("env") or []) if str(x).strip())
    config = tuple(str(x).strip() for x in list(row.get("config") or []) if str(x).strip())
    return HookRequiresSpec(bins=bins, any_bins=any_bins, env=env, config=config)


def _parse_metadata_obj(raw: Any) -> HookMetadataSpec:
    row = raw if isinstance(raw, dict) else {}
    node_script: bool | None
    if "nodeScript" in row:
        node_script = bool(row.get("nodeScript"))
    else:
        node_script = None
    hm = row.get("hookMode")
    hook_mode = str(hm).strip() if isinstance(hm, str) and str(hm).strip() else None
    return HookMetadataSpec(
        events=tuple(str(x).strip() for x in list(row.get("events") or []) if str(x).strip()),
        always=bool(row["always"]) if isinstance(row.get("always"), bool) else None,
        emoji=str(row.get("emoji")).strip() if isinstance(row.get("emoji"), str) else None,
        homepage=str(row.get("homepage")).strip() if isinstance(row.get("homepage"), str) else None,
        hook_key=str(row.get("hookKey")).strip() if isinstance(row.get("hookKey"), str) else None,
        export=str(row.get("export")).strip() if isinstance(row.get("export"), str) else None,
        os=tuple(str(x).strip() for x in list(row.get("os") or []) if str(x).strip()),
        requires=_parse_requires_obj(row.get("requires")),
        install=(),
        hook_mode=hook_mode,
        node_script=node_script,
    )


def should_include_hook(
    *, entry: HookEntry, config: Optional[Dict[str, Any]], eligibility: Optional[HookEligibilityContext] = None
) -> bool:
    metadata = _parse_metadata_obj(entry.metadata)
    hook_name = str(entry.hook.name or "").strip()
    hook_key = str(metadata.hook_key or hook_name).strip() or hook_name
    hook_cfg = resolve_hook_config(config, hook_key)

    if not resolve_hook_enable_state(entry, config).get("enabled"):
        return False

    remote = (eligibility or {}).get("remote") if isinstance(eligibility, dict) else None
    remote_platforms: list[str] = []
    if isinstance(remote, dict):
        rp = remote.get("platforms")
        if isinstance(rp, list):
            remote_platforms = [str(x).strip() for x in rp if str(x or "").strip()]
    if not _hook_os_gate_satisfied(hook_os=metadata.os, remote_platforms=remote_platforms):
        return False

    req = metadata.requires or HookRequiresSpec()
    bins = list(req.bins)
    for b in bins:
        if remote and callable(remote.get("hasBin")):
            if not bool(remote["hasBin"](b)):
                return False
            continue
        if not _has_binary(b):
            return False

    any_bins = list(req.any_bins)
    if any_bins:
        if remote and callable(remote.get("hasAnyBin")):
            if not bool(remote["hasAnyBin"](any_bins)):
                return False
        elif not any(_has_binary(b) for b in any_bins):
            return False

    env_req = list(req.env)
    hook_env = hook_cfg.get("env") if isinstance(hook_cfg, dict) and isinstance(hook_cfg.get("env"), dict) else {}
    for env_name in env_req:
        if os.getenv(env_name) or hook_env.get(env_name):
            continue
        return False

    config_req = list(req.config)
    for cfg_path in config_req:
        if not _is_config_path_truthy(config, cfg_path):
            return False

    return True


def should_include_hook_compat(
    *,
    entry: HookEntry | Dict[str, Any],
    config: Optional[Dict[str, Any]],
    eligibility: Optional[HookEligibilityContext] = None,
) -> bool:
    return should_include_hook(entry=ensure_hook_entry(entry), config=config, eligibility=eligibility)

