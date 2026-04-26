from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple

from .frontmatter import resolve_hook_key
from .hook_types import HookEntry, HookSource, ensure_entry_dict, ensure_hook_entry


@dataclass(frozen=True, slots=True)
class HookSourcePolicy:
    precedence: int
    trustedLocalCode: bool
    defaultEnableMode: Literal["default-on", "explicit-opt-in"]
    canOverride: Tuple[HookSource, ...]
    canBeOverriddenBy: Tuple[HookSource, ...]


HOOK_SOURCE_POLICIES: Dict[HookSource, HookSourcePolicy] = {
    "oclaw-bundled": HookSourcePolicy(
        precedence=10,
        trustedLocalCode=True,
        defaultEnableMode="default-on",
        canOverride=("oclaw-bundled",),
        canBeOverriddenBy=("oclaw-managed", "oclaw-plugin"),
    ),
    "oclaw-plugin": HookSourcePolicy(
        precedence=20,
        trustedLocalCode=True,
        defaultEnableMode="default-on",
        canOverride=("oclaw-bundled", "oclaw-plugin"),
        canBeOverriddenBy=("oclaw-managed",),
    ),
    "oclaw-managed": HookSourcePolicy(
        precedence=30,
        trustedLocalCode=True,
        defaultEnableMode="default-on",
        canOverride=("oclaw-bundled", "oclaw-managed", "oclaw-plugin"),
        canBeOverriddenBy=("oclaw-managed",),
    ),
    "oclaw-workspace": HookSourcePolicy(
        precedence=40,
        trustedLocalCode=True,
        defaultEnableMode="explicit-opt-in",
        canOverride=("oclaw-workspace",),
        canBeOverriddenBy=("oclaw-workspace",),
    ),
}


def get_hook_source_policy(source: HookSource) -> HookSourcePolicy:
    return HOOK_SOURCE_POLICIES[source]


def resolve_hook_config(config: Optional[Dict[str, Any]], hook_key: str) -> Optional[Dict[str, Any]]:
    if not config or not isinstance(config, dict):
        return None
    hooks = (((config.get("hooks") or {}).get("internal") or {}).get("entries"))  # type: ignore[assignment]
    if not isinstance(hooks, dict):
        return None
    entry = hooks.get(hook_key)
    return entry if isinstance(entry, dict) else None


def resolve_hook_enable_state(entry: HookEntry | Dict[str, Any], config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Returns { enabled: bool, reason?: str }
    """
    entry_dict = ensure_entry_dict(entry)
    hook = entry_dict.get("hook") if isinstance(entry_dict, dict) else None
    name = (hook or {}).get("name") if isinstance(hook, dict) else None
    source = (hook or {}).get("source") if isinstance(hook, dict) else None
    if not isinstance(name, str) or not isinstance(source, str):
        return {"enabled": False, "reason": "invalid hook entry"}

    hook_key = resolve_hook_key(name, entry_dict)
    hook_cfg = resolve_hook_config(config, hook_key)
    invocation = entry_dict.get("invocation") if isinstance(entry_dict.get("invocation"), dict) else {}

    if source == "oclaw-plugin":
        return {"enabled": True}

    if invocation.get("enabled") is False:
        return {"enabled": False, "reason": "disabled by hook invocation policy"}

    if isinstance(hook_cfg, dict) and hook_cfg.get("enabled") is False:
        return {"enabled": False, "reason": "disabled in config"}

    policy = get_hook_source_policy(source)  # type: ignore[arg-type]
    if policy.defaultEnableMode == "explicit-opt-in":
        if not isinstance(hook_cfg, dict) or hook_cfg.get("enabled") is not True:
            return {"enabled": False, "reason": "workspace hook (disabled by default)"}
    return {"enabled": True}


def _can_override(candidate: HookEntry | Dict[str, Any], existing: HookEntry | Dict[str, Any]) -> bool:
    c_dict = ensure_entry_dict(candidate)
    e_dict = ensure_entry_dict(existing)
    c_source = ((c_dict.get("hook") or {}).get("source")) if isinstance(c_dict, dict) else None
    e_source = ((e_dict.get("hook") or {}).get("source")) if isinstance(e_dict, dict) else None
    if c_source not in HOOK_SOURCE_POLICIES or e_source not in HOOK_SOURCE_POLICIES:
        return False
    c_pol = get_hook_source_policy(c_source)  # type: ignore[arg-type]
    e_pol = get_hook_source_policy(e_source)  # type: ignore[arg-type]
    return (e_source in c_pol.canOverride) and (c_source in e_pol.canBeOverriddenBy)


def resolve_hook_entries(
    entries: Sequence[HookEntry | Dict[str, Any]],
    on_collision_ignored: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> List[HookEntry]:
    ordered = sorted(
        list(enumerate(entries)),
        key=lambda x: (
            get_hook_source_policy(
                str((ensure_entry_dict(x[1]).get("hook") or {}).get("source") or "oclaw-managed")  # type: ignore[arg-type]
            ).precedence,
            x[0],
        ),
    )
    merged: Dict[str, HookEntry] = {}
    for _, entry in ordered:
        name = ensure_entry_dict(entry).get("hook", {}).get("name")
        if not isinstance(name, str):
            continue
        existing = merged.get(name)
        if not existing:
            merged[name] = ensure_hook_entry(entry)
            continue
        if _can_override(entry, existing):
            merged[name] = ensure_hook_entry(entry)
            continue
        if on_collision_ignored:
            on_collision_ignored(
                {"name": name, "kept": ensure_entry_dict(existing), "ignored": ensure_entry_dict(entry)}
            )
    return list(merged.values())


def resolve_hook_entries_compat(
    entries: Sequence[HookEntry | Dict[str, Any]],
    on_collision_ignored: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> List[Dict[str, Any]]:
    resolved = resolve_hook_entries(entries, on_collision_ignored=on_collision_ignored)
    return [ensure_entry_dict(e) for e in resolved]

