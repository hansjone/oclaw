from __future__ import annotations

import json
import os
from typing import Any

from oclaw.openclaw_runtime.skill_role_binding import (
    allowed_workspace_skill_names_for_role,
    should_apply_workspace_role_filter,
)
from oclaw.openclaw_runtime.skills import (
    _allowed_tool_names_after_wire_policy,
    build_skill_manifest,
    discover_workspace_skill_manifests,
)
from oclaw.tools.base import ToolRegistry


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
) -> list[tuple[str, str, str]]:
    """Return (name, description, location) for model-visible skills (wire + disable filtered)."""
    allowed, _hidden = _allowed_tool_names_after_wire_policy(registry=registry, store=store, base_url=base_url)
    disabled = _disabled_skill_names(store)
    skill_specs, _stats = build_skill_manifest(registry=registry, store=store, base_url=base_url)
    seen: set[str] = set()
    out: list[tuple[str, str, str]] = []

    role_filter = should_apply_workspace_role_filter(store=store, skill_binding_role=skill_binding_role)
    role_allow: set[str] = set()
    if role_filter:
        role_allow = allowed_workspace_skill_names_for_role(store=store, role=str(skill_binding_role or ""))

    for m in sorted(discover_workspace_skill_manifests(), key=lambda x: x.name.lower()):
        if m.disable_model_invocation or m.name in disabled:
            continue
        if role_filter:
            if m.name not in role_allow:
                continue
        elif m.name not in allowed:
            continue
        out.append((m.name, (m.description or "").strip() or m.name, m.skill_file))
        seen.add(m.name)

    for s in sorted(skill_specs, key=lambda x: x.name.lower()):
        if s.name in seen or s.name in disabled:
            continue
        out.append((s.name, (s.description or "").strip() or s.name, str(s.location or f"tool:{s.name}")))
        seen.add(s.name)

    return sorted(out, key=lambda x: x[0].lower())


def format_skills_for_prompt(entries: list[tuple[str, str, str]], *, max_chars: int) -> str:
    """oclaw-aligned `<available_skills>` XML block with a hard character budget."""
    if not entries or max_chars <= 0:
        return ""
    header = (
        "\n\nThe following skills describe callable capabilities and optional workspace packages.\n"
        "When you need full instructions for a workspace skill, use `read_file` (or equivalent) on the path in `<location>`.\n"
        "For execution, use native tool/function calls provided by the host.\n"
        "When a skill references a relative path, resolve it against that skill's directory (parent of SKILL.md).\n"
    )
    tail = "\n</available_skills>"

    def _render(subset: list[tuple[str, str, str]]) -> str:
        lines = [header.rstrip(), "", "<available_skills>"]
        for name, desc, loc in subset:
            lines.append("  <skill>")
            lines.append(f"    <name>{escape_xml(name)}</name>")
            lines.append(f"    <description>{escape_xml(desc)}</description>")
            lines.append(f"    <location>{escape_xml(loc)}</location>")
            lines.append("  </skill>")
        lines.append("</available_skills>")
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
) -> str:
    if not _skill_runtime_enabled(store) or not _skills_prompt_in_system_enabled(store):
        return ""
    entries = collect_skill_catalog_entries(
        store=store,
        registry=registry,
        base_url=base_url,
        skill_binding_role=skill_binding_role,
    )
    return format_skills_for_prompt(entries, max_chars=_max_skills_prompt_chars())


__all__ = [
    "build_skills_catalog_block",
    "collect_skill_catalog_entries",
    "escape_xml",
    "format_skills_for_prompt",
]
