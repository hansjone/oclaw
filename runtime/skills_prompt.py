from __future__ import annotations

import json
import os
from typing import Any

from runtime.skill_role_binding import (
    allowed_workspace_skill_names_for_role,
    should_apply_workspace_role_filter,
)
from runtime.skills import discover_workspace_skill_manifests
from runtime.skills_workspace_lane import skill_dir_private_lane_segment
from runtime.tools.base import ToolRegistry


def _skill_runtime_enabled(store: Any) -> bool:
    try:
        raw_flag = str(store.get_setting("AIA_SKILL_RUNTIME_ENABLED") or "").strip().lower()
        if raw_flag:
            return raw_flag in {"1", "true", "yes", "on"}
    except Exception:
        pass
    return True


def _skills_prompt_in_system_enabled(store: Any) -> bool:
    raw = str(os.getenv("AIA_SKILLS_PROMPT_IN_SYSTEM") or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    try:
        s = str(store.get_setting("AIA_SKILLS_PROMPT_IN_SYSTEM") or "").strip().lower()
        if s in {"0", "false", "no", "off"}:
            return False
    except Exception:
        pass
    return True


def _disabled_skill_names(store: Any) -> set[str]:
    try:
        raw_disabled = str(store.get_setting("AIA_SKILL_DISABLED_NAMES") or "").strip()
        if raw_disabled:
            arr = json.loads(raw_disabled)
            if isinstance(arr, list):
                return {str(x).strip() for x in arr if str(x).strip()}
    except Exception:
        pass
    return set()


def _max_skills_prompt_chars() -> int:
    try:
        return max(0, min(int(os.getenv("AIA_SKILLS_PROMPT_MAX_CHARS", "18000")), 500_000))
    except Exception:
        return 18_000


def escape_xml(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def collect_skill_catalog_entries(
    *,
    store: Any,
    registry: ToolRegistry,
    base_url: str,
    skill_binding_role: str | None = None,
    exclude_foreign_private_workspace_skills: bool = False,
    private_workspace_lane_segment: str | None = None,
) -> list[tuple[str, str, str]]:
    """Return (name, description, location) for model-visible prompt skills."""
    _ = registry
    _ = base_url
    disabled = _disabled_skill_names(store)
    out: list[tuple[str, str, str]] = []

    role_filter = should_apply_workspace_role_filter(store=store, skill_binding_role=skill_binding_role)
    role_allow: set[str] = set()
    if role_filter:
        role_allow = allowed_workspace_skill_names_for_role(store=store, role=str(skill_binding_role or ""))

    for m in sorted(discover_workspace_skill_manifests(), key=lambda x: x.name.lower()):
        if m.disable_model_invocation or m.name in disabled:
            continue
        priv_lane = skill_dir_private_lane_segment(str(m.skill_dir or ""))
        want_lane = str(private_workspace_lane_segment or "").strip()
        if exclude_foreign_private_workspace_skills:
            if priv_lane is not None:
                if not want_lane or priv_lane != want_lane:
                    continue
        own_private_lane = bool(
            exclude_foreign_private_workspace_skills
            and priv_lane is not None
            and want_lane
            and priv_lane == want_lane
        )
        if role_filter:
            if m.name not in role_allow and not own_private_lane:
                continue
        out.append((m.name, (m.description or "").strip() or m.name, m.skill_file))

    return sorted(out, key=lambda x: x[0].lower())


def format_skills_for_prompt(entries: list[tuple[str, str, str]], *, max_chars: int) -> str:
    """Natural-language skill catalog block with a hard character budget."""
    if not entries or max_chars <= 0:
        return ""

    def _render(subset: list[tuple[str, str, str]]) -> str:
        lines: list[str] = ['']
        lines.append("\n## 技能（skills）：")
        for name, desc, loc in subset:
            safe_name = str(name).replace('"', '\\"')
            safe_desc = str(desc).replace('"', '\\"')
            safe_loc = str(loc).replace('"', '\\"')
            lines.append(f'- name:"{safe_name}", description:"{safe_desc}", path:"{safe_loc}"')
        return "\n".join(lines)

    # Drop from the end until under budget (keep workspace-first order).
    subset = list(entries)
    while subset:
        blob = _render(subset)
        if len(blob) <= max_chars:
            return blob
        subset = subset[:-1]
    return ""


def build_skills_catalog_block(
    *,
    store: Any,
    registry: ToolRegistry,
    base_url: str,
    skill_binding_role: str | None = None,
    exclude_foreign_private_workspace_skills: bool = False,
    private_workspace_lane_segment: str | None = None,
) -> str:
    if not _skill_runtime_enabled(store) or not _skills_prompt_in_system_enabled(store):
        return ""
    entries = collect_skill_catalog_entries(
        store=store,
        registry=registry,
        base_url=base_url,
        skill_binding_role=skill_binding_role,
        exclude_foreign_private_workspace_skills=exclude_foreign_private_workspace_skills,
        private_workspace_lane_segment=private_workspace_lane_segment,
    )
    return format_skills_for_prompt(entries, max_chars=_max_skills_prompt_chars())


__all__ = [
    "build_skills_catalog_block",
    "collect_skill_catalog_entries",
    "escape_xml",
    "format_skills_for_prompt",
]
