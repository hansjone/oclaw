from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple

from .frontmatter import resolve_hook_key

HookSource = Literal["openclaw-bundled", "openclaw-plugin", "openclaw-managed", "openclaw-workspace"]


@dataclass(frozen=True, slots=True)
class HookSourcePolicy:
    precedence: int
    trustedLocalCode: bool
    defaultEnableMode: Literal["default-on", "explicit-opt-in"]
    canOverride: Tuple[HookSource, ...]
    canBeOverriddenBy: Tuple[HookSource, ...]


HOOK_SOURCE_POLICIES: Dict[HookSource, HookSourcePolicy] = {
    "openclaw-bundled": HookSourcePolicy(
        precedence=10,
        trustedLocalCode=True,
        defaultEnableMode="default-on",
        canOverride=("openclaw-bundled",),
        canBeOverriddenBy=("openclaw-managed", "openclaw-plugin"),
    ),
    "openclaw-plugin": HookSourcePolicy(
        precedence=20,
        trustedLocalCode=True,
        defaultEnableMode="default-on",
        canOverride=("openclaw-bundled", "openclaw-plugin"),
        canBeOverriddenBy=("openclaw-managed",),
    ),
    "openclaw-managed": HookSourcePolicy(
        precedence=30,
        trustedLocalCode=True,
        defaultEnableMode="default-on",
        canOverride=("openclaw-bundled", "openclaw-managed", "openclaw-plugin"),
        canBeOverriddenBy=("openclaw-managed",),
    ),
    "openclaw-workspace": HookSourcePolicy(
        precedence=40,
        trustedLocalCode=True,
        defaultEnableMode="explicit-opt-in",
        canOverride=("openclaw-workspace",),
        canBeOverriddenBy=("openclaw-workspace",),
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


def resolve_hook_enable_state(entry: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Returns { enabled: bool, reason?: str }
    """
    hook = entry.get("hook") if isinstance(entry, dict) else None
    name = (hook or {}).get("name") if isinstance(hook, dict) else None
    source = (hook or {}).get("source") if isinstance(hook, dict) else None
    if not isinstance(name, str) or not isinstance(source, str):
        return {"enabled": False, "reason": "invalid hook entry"}

    hook_key = resolve_hook_key(name, entry)
    hook_cfg = resolve_hook_config(config, hook_key)

    if source == "openclaw-plugin":
        return {"enabled": True}

    if isinstance(hook_cfg, dict) and hook_cfg.get("enabled") is False:
        return {"enabled": False, "reason": "disabled in config"}

    policy = get_hook_source_policy(source)  # type: ignore[arg-type]
    if policy.defaultEnableMode == "explicit-opt-in":
        if not isinstance(hook_cfg, dict) or hook_cfg.get("enabled") is not True:
            return {"enabled": False, "reason": "workspace hook (disabled by default)"}
    return {"enabled": True}


def _can_override(candidate: Dict[str, Any], existing: Dict[str, Any]) -> bool:
    c_source = ((candidate.get("hook") or {}).get("source")) if isinstance(candidate, dict) else None
    e_source = ((existing.get("hook") or {}).get("source")) if isinstance(existing, dict) else None
    if c_source not in HOOK_SOURCE_POLICIES or e_source not in HOOK_SOURCE_POLICIES:
        return False
    c_pol = get_hook_source_policy(c_source)  # type: ignore[arg-type]
    e_pol = get_hook_source_policy(e_source)  # type: ignore[arg-type]
    return (e_source in c_pol.canOverride) and (c_source in e_pol.canBeOverriddenBy)


def resolve_hook_entries(
    entries: Sequence[Dict[str, Any]],
    on_collision_ignored: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> List[Dict[str, Any]]:
    ordered = sorted(
        list(enumerate(entries)),
        key=lambda x: (get_hook_source_policy(x[1]["hook"]["source"]).precedence, x[0]),  # type: ignore[index]
    )
    merged: Dict[str, Dict[str, Any]] = {}
    for _, entry in ordered:
        name = entry.get("hook", {}).get("name")
        if not isinstance(name, str):
            continue
        existing = merged.get(name)
        if not existing:
            merged[name] = entry
            continue
        if _can_override(entry, existing):
            merged[name] = entry
            continue
        if on_collision_ignored:
            on_collision_ignored({"name": name, "kept": existing, "ignored": entry})
    return list(merged.values())

