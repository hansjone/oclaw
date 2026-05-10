from __future__ import annotations

import json
import os
from typing import Any

from oclaw.runtime.agents.specialists import discover_specialist_ids

SKILL_ROLE_BINDING_KEY = "skill_role_binding"
SKILL_ROLE_BINDING_ENABLED_SETTING = "AIA_SKILL_ROLE_BINDING_ENABLED"
SKILL_ROLE_BINDING_MANAGER_INHERIT_SETTING = "AIA_SKILL_ROLE_BINDING_MANAGER_INHERIT"


def _truthy(v: str | None) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "on"}


def ordered_specialist_ids() -> list[str]:
    base = [str(k).strip().lower() for k in discover_specialist_ids() if str(k).strip()]
    preferred = [x for x in ("generalist", "ops", "memory", "image", "video") if x in set(base)]
    return preferred + [x for x in base if x not in set(preferred)]


def ordered_binding_roles() -> list[str]:
    return ["manager", *ordered_specialist_ids()]


def skill_role_binding_enabled(*, store: Any) -> bool:
    raw_env = str(os.getenv(SKILL_ROLE_BINDING_ENABLED_SETTING) or "").strip()
    if raw_env:
        return _truthy(raw_env)
    try:
        raw = str(store.get_setting(SKILL_ROLE_BINDING_ENABLED_SETTING) or "").strip()
    except Exception:
        raw = ""
    return _truthy(raw) if raw else False


def load_skill_role_binding_dict(store: Any) -> dict[str, Any]:
    try:
        raw = str(store.get_setting(SKILL_ROLE_BINDING_KEY) or "").strip()
    except Exception:
        raw = ""
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def mapping_has_any_skill_names(mapping: dict[str, list[str]]) -> bool:
    for vals in mapping.values():
        if vals and any(str(x).strip() for x in vals):
            return True
    return False


def normalize_skill_role_binding(
    *,
    mapping_raw: dict[str, Any],
    valid_skill_names: set[str],
    available_roles: list[str] | None = None,
) -> dict[str, list[str]]:
    roles = available_roles if available_roles is not None else ordered_binding_roles()
    role_set = set(roles)
    out: dict[str, list[str]] = {r: [] for r in roles}
    for k, v in (mapping_raw or {}).items():
        rk = str(k or "").strip().lower()
        if rk not in role_set:
            continue
        items = v if isinstance(v, list) else []
        seen: set[str] = set()
        for x in items:
            nm = str(x or "").strip()
            if not nm or nm not in valid_skill_names or nm in seen:
                continue
            seen.add(nm)
            out[rk].append(nm)
    return out


def allowed_workspace_skill_names_for_role(*, store: Any, role: str) -> set[str]:
    """Union of manager-bound skills and skills bound to the given specialist role."""
    r = str(role or "").strip().lower()
    if not r:
        return set()
    from oclaw.runtime.skills import discover_public_workspace_skill_names

    public = discover_public_workspace_skill_names()
    mapping = normalize_skill_role_binding(
        mapping_raw=load_skill_role_binding_dict(store),
        valid_skill_names=_all_installed_skill_names(store),
    )
    try:
        raw_env = str(os.getenv(SKILL_ROLE_BINDING_MANAGER_INHERIT_SETTING) or "").strip()
        if raw_env:
            inherit_mgr = _truthy(raw_env)
        else:
            raw = str(store.get_setting(SKILL_ROLE_BINDING_MANAGER_INHERIT_SETTING) or "").strip()
            inherit_mgr = _truthy(raw) if raw else True
    except Exception:
        inherit_mgr = True
    mgr = {str(x).strip() for x in (mapping.get("manager") or []) if str(x).strip()} if inherit_mgr else set()
    sp = {str(x).strip() for x in (mapping.get(r) or []) if str(x).strip()}
    return mgr | sp | public


def _all_installed_skill_names(store: Any) -> set[str]:
    from oclaw.runtime.skills import discover_workspace_skill_manifests

    return {str(m.name).strip() for m in discover_workspace_skill_manifests() if str(m.name or "").strip()}


def should_apply_workspace_role_filter(*, store: Any, skill_binding_role: str | None) -> bool:
    if not str(skill_binding_role or "").strip():
        return False
    if not skill_role_binding_enabled(store=store):
        return False
    raw = load_skill_role_binding_dict(store)
    normalized = normalize_skill_role_binding(
        mapping_raw=raw,
        valid_skill_names=_all_installed_skill_names(store),
    )
    if not mapping_has_any_skill_names(normalized):
        return False
    return True


__all__ = [
    "SKILL_ROLE_BINDING_KEY",
    "SKILL_ROLE_BINDING_ENABLED_SETTING",
    "SKILL_ROLE_BINDING_MANAGER_INHERIT_SETTING",
    "allowed_workspace_skill_names_for_role",
    "load_skill_role_binding_dict",
    "mapping_has_any_skill_names",
    "normalize_skill_role_binding",
    "ordered_binding_roles",
    "ordered_specialist_ids",
    "should_apply_workspace_role_filter",
    "skill_role_binding_enabled",
]
