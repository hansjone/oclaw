from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.platform.config.runtime_paths import runtime_skills_root
from oclaw.prompts.frontmatter import parse_frontmatter_dict, split_markdown_frontmatter
from oclaw.runtime.skill_manifest_core import (
    SkillInstallSpec,
    normalize_frontmatter,
    parse_skill_frontmatter,
)

if TYPE_CHECKING:
    from oclaw.runtime.tools.base import ToolRegistry, ToolSpec


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    read_only: bool = False
    tags: tuple[str, ...] = ()
    origin: str = "builtin"
    location: str = ""
    install_spec_count: int = 0
    model_invocable: bool = True

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


@dataclass(frozen=True)
class SkillManifest:
    name: str
    description: str
    skill_dir: str
    skill_file: str
    user_invocable: bool = True
    disable_model_invocation: bool = False
    metadata_oclaw: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    install: tuple[SkillInstallSpec, ...] = ()
    body: str = ""


class SkillRegistry:
    def __init__(self, skills: tuple[SkillSpec, ...] | list[SkillSpec] | None = None):
        self._skills: dict[str, SkillSpec] = {}
        if skills:
            for s in skills:
                self.register(s)

    def register(self, skill: SkillSpec) -> None:
        self._skills[str(skill.name)] = skill

    def get(self, name: str) -> SkillSpec | None:
        return self._skills.get(str(name))

    def list(self) -> tuple[SkillSpec, ...]:
        return tuple(self._skills.values())

    def as_openai_tools(self) -> list[dict[str, Any]]:
        return [s.as_openai_tool() for s in self.list()]


def default_skills_root() -> Path:
    raw = str(os.getenv("AIA_SKILLS_ROOT") or "").strip()
    if raw:
        return Path(raw).resolve()
    preferred = runtime_skills_root()
    if preferred.exists() and preferred.is_dir():
        return preferred
    # Optional hard-disable for legacy fallback lookups.
    if str(os.getenv("AIA_DISABLE_LEGACY_SKILLS_FALLBACK") or "").strip().lower() in {"1", "true", "yes", "on"}:
        return preferred
    typo_legacy = (PROJECT_ROOT / "sills").resolve()
    if typo_legacy.exists() and typo_legacy.is_dir():
        return typo_legacy
    legacy = (PROJECT_ROOT / "skills").resolve()
    if legacy.exists() and legacy.is_dir():
        return legacy
    legacy_parent = (PROJECT_ROOT.parent / "skills").resolve()
    if legacy_parent.exists() and legacy_parent.is_dir():
        return legacy_parent
    return preferred


def _parse_skill_frontmatter_block(frontmatter_text: str) -> dict[str, Any]:
    raw_fm = str(frontmatter_text or "").strip()
    if not raw_fm:
        return {}
    fm = parse_frontmatter_dict(raw_fm, source="skill")
    return normalize_frontmatter(fm)


def load_skill_manifest(skill_dir: str | Path) -> SkillManifest | None:
    root = Path(skill_dir).resolve()
    f = root / "SKILL.md"
    if not f.exists() or not f.is_file():
        return None
    raw = f.read_text(encoding="utf-8", errors="ignore")
    fm_text, body = split_markdown_frontmatter(raw)
    fm = _parse_skill_frontmatter_block(fm_text)
    parsed = parse_skill_frontmatter(fm=fm, default_name=root.name)
    return SkillManifest(
        name=parsed.name,
        description=parsed.description,
        skill_dir=str(root),
        skill_file=str(f),
        user_invocable=parsed.user_invocable,
        disable_model_invocation=parsed.disable_model_invocation,
        metadata_oclaw=parsed.metadata_oclaw,
        runtime=parsed.runtime.as_dict() if parsed.runtime else {},
        install=parsed.install,
        body=str(body or ""),
    )


def discover_workspace_skill_manifests(skills_root: str | Path | None = None) -> tuple[SkillManifest, ...]:
    base = Path(skills_root).resolve() if skills_root else default_skills_root()
    if not base.exists() or not base.is_dir():
        return ()
    out: list[SkillManifest] = []
    seen_files: set[str] = set()
    for skill_md in sorted(base.rglob("SKILL.md"), key=lambda p: str(p).lower()):
        d = skill_md.parent
        m = load_skill_manifest(d)
        if m:
            k = str(Path(m.skill_file).resolve())
            if k in seen_files:
                continue
            seen_files.add(k)
            out.append(m)
    return tuple(out)


def discover_public_workspace_skill_names(skills_root: str | Path | None = None) -> set[str]:
    """Skill names under `<skills_root>/_workspace/public/<skill>/SKILL.md`.

    These skills are treated as public and do not require role binding.
    """
    base = Path(skills_root).resolve() if skills_root else default_skills_root()
    public_root = (base / "_workspace" / "public").resolve()
    if not public_root.exists() or not public_root.is_dir():
        return set()
    out: set[str] = set()
    try:
        for md in public_root.rglob("SKILL.md"):
            if not md.is_file():
                continue
            m = load_skill_manifest(md.parent)
            if m and str(m.name or "").strip():
                out.add(str(m.name).strip())
    except Exception:
        return set()
    return out


def _tool_origin(tool: "ToolSpec") -> str:
    nm = str(getattr(tool, "name", "") or "")
    if nm.startswith("mcp__"):
        return "mcp"
    tags = set(getattr(tool, "tags", frozenset()) or frozenset())
    if "plugin" in tags:
        return "plugin"
    return "builtin"


def _allowed_tool_names_after_wire_policy(
    *,
    registry: "ToolRegistry",
    store: Any,
    base_url: str,
) -> tuple[set[str], list[str]]:
    raw = registry.as_openai_tools()
    try:
        from oclaw.platform.llm.tool_wire_policy import prepare_openai_tools_for_llm_api

        prepared = prepare_openai_tools_for_llm_api(
            raw,
            base_url=base_url,
            store=store,
            max_json_bytes=None,
            role=None,
        )
    except Exception:
        prepared = raw

    allowed: set[str] = set()
    for e in prepared or []:
        if not isinstance(e, dict) or str(e.get("type") or "") != "function":
            continue
        fn = e.get("function")
        if not isinstance(fn, dict):
            continue
        nm = str(fn.get("name") or "").strip()
        if nm:
            allowed.add(nm)

    all_names = {str((t.get("function") or {}).get("name") or "") for t in (raw or []) if isinstance(t, dict)}
    all_names.discard("")
    hidden = sorted([n for n in all_names if n and n not in allowed])
    return allowed or all_names, hidden


def build_skill_manifest(
    *,
    registry: "ToolRegistry",
    store: Any,
    base_url: str = "",
) -> tuple[tuple[SkillSpec, ...], dict[str, Any]]:
    allowed, hidden = _allowed_tool_names_after_wire_policy(registry=registry, store=store, base_url=base_url)
    disabled_names: set[str] = set()
    try:
        raw_disabled = str(store.get_setting("AIA_SKILL_DISABLED_NAMES") or "").strip()
        if raw_disabled:
            arr = json.loads(raw_disabled)
            if isinstance(arr, list):
                disabled_names = {str(x).strip() for x in arr if str(x).strip()}
    except Exception:
        disabled_names = set()

    manifests = list(discover_workspace_skill_manifests())
    manifest_by_name = {m.name: m for m in manifests}
    workspace_skill_names = sorted(
        {
            str(m.name).strip()
            for m in manifests
            if str(getattr(m, "name", "") or "").strip()
            and not bool(getattr(m, "disable_model_invocation", False))
        }
    )
    skills: list[SkillSpec] = []
    for t in sorted((registry.list() or []), key=lambda x: str(getattr(x, "name", "") or "").lower()):
        name = str(getattr(t, "name", "") or "").strip()
        if not name or name not in allowed or name in disabled_names:
            continue
        desc = str(getattr(t, "description", "") or "")
        params = getattr(t, "parameters", None)
        schema = dict(params) if isinstance(params, dict) else {"type": "object", "additionalProperties": True}
        tags = tuple(sorted({str(x) for x in (getattr(t, "tags", frozenset()) or frozenset()) if str(x)}))
        m = manifest_by_name.get(name)
        location = str(m.skill_file) if m is not None else f"tool:{name}"
        install_spec_count = int(len(m.install)) if m is not None else 0
        model_invocable = not bool(m.disable_model_invocation) if m is not None else True
        skills.append(
            SkillSpec(
                name=name,
                description=desc,
                input_schema=schema,
                read_only=bool(getattr(t, "read_only", False) or getattr(t, "is_read_only", lambda: False)()),
                tags=tags,
                origin=_tool_origin(t),
                location=location,
                install_spec_count=install_spec_count,
                model_invocable=model_invocable,
            )
        )

    skills = sorted(skills, key=lambda x: x.name.lower())
    hidden_mcp = [n for n in hidden if n.startswith("mcp__")]
    stats = {
        "skills_total": len(skills),
        "hidden_total": len(hidden),
        "hidden_mcp_total": len(hidden_mcp),
        "hidden_mcp_preview": hidden_mcp[:20],
        "disabled_total": len(disabled_names),
        "visible_names_preview": [s.name for s in skills[:30]],
        "workspace_skill_names_preview": workspace_skill_names[:60],
    }
    try:
        json.dumps(stats, ensure_ascii=False, default=str)
    except Exception:
        stats = {"skills_total": len(skills)}
    return tuple(skills), stats


def build_skill_registry(
    *,
    registry: ToolRegistry,
    store: Any,
    base_url: str = "",
) -> tuple[SkillRegistry, dict[str, Any]]:
    skills, stats = build_skill_manifest(registry=registry, store=store, base_url=base_url)
    return SkillRegistry(skills), stats


def materialize_skills_from_tool_specs(
    tools: list["ToolSpec"],
) -> tuple[SkillSpec, ...]:
    out: list[SkillSpec] = []
    for t in tools or []:
        name = str(getattr(t, "name", "") or "").strip()
        if not name:
            continue
        desc = str(getattr(t, "description", "") or "")
        params = getattr(t, "parameters", None)
        schema = dict(params) if isinstance(params, dict) else {"type": "object", "additionalProperties": True}
        tags = tuple(sorted({str(x) for x in (getattr(t, "tags", frozenset()) or frozenset()) if str(x)}))
        out.append(
            SkillSpec(
                name=name,
                description=desc,
                input_schema=schema,
                read_only=bool(getattr(t, "read_only", False) or getattr(t, "is_read_only", lambda: False)()),
                tags=tags,
                origin=_tool_origin(t),
            )
        )
    return tuple(out)


def skill_runtime_diagnostics() -> dict[str, Any]:
    root = default_skills_root()
    manifests = discover_workspace_skill_manifests(root)
    return {
        "skills_root": str(root),
        "skills_total": len(manifests),
        "skills_names": [m.name for m in manifests],
        "skills_files": [m.skill_file for m in manifests],
    }


__all__ = [
    "SkillSpec",
    "SkillInstallSpec",
    "SkillManifest",
    "SkillRegistry",
    "build_skill_manifest",
    "build_skill_registry",
    "default_skills_root",
    "discover_workspace_skill_manifests",
    "load_skill_manifest",
    "materialize_skills_from_tool_specs",
    "skill_runtime_diagnostics",
]
