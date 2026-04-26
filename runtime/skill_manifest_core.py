from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillInstallSpec:
    id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillRuntimeSpec:
    type: str
    entry: str
    schema: dict[str, Any] = field(default_factory=dict)
    permissions: dict[str, Any] = field(default_factory=dict)
    timeout_s: float | None = None
    max_output_bytes: int | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type, "entry": self.entry}
        if self.schema:
            out["schema"] = dict(self.schema)
        if self.permissions:
            out["permissions"] = dict(self.permissions)
        if isinstance(self.timeout_s, (int, float)):
            out["timeout_s"] = float(self.timeout_s)
        if isinstance(self.max_output_bytes, int):
            out["max_output_bytes"] = int(self.max_output_bytes)
        return out


@dataclass(frozen=True)
class ParsedSkillFrontmatter:
    name: str
    description: str
    user_invocable: bool
    disable_model_invocation: bool
    metadata_oclaw: dict[str, Any]
    install: tuple[SkillInstallSpec, ...]
    runtime: SkillRuntimeSpec | None


def normalize_frontmatter(fm: dict[str, Any]) -> dict[str, Any]:
    out = dict(fm)
    md = out.get("metadata")
    if isinstance(md, str) and md.strip():
        try:
            out["metadata"] = json.loads(md)
        except Exception:
            out["metadata"] = {}
    elif not isinstance(md, dict):
        out["metadata"] = {}
    for key, default in (("user-invocable", True), ("disable-model-invocation", False)):
        val = out.get(key, default)
        if isinstance(val, bool):
            out[key] = val
        else:
            out[key] = str(val or str(default)).strip().lower() in {"1", "true", "yes", "on"}
    return out


def parse_install_specs(metadata_oclaw: dict[str, Any]) -> tuple[SkillInstallSpec, ...]:
    raw = metadata_oclaw.get("install")
    if not isinstance(raw, list):
        return ()
    out: list[SkillInstallSpec] = []
    for idx, it in enumerate(raw):
        if not isinstance(it, dict):
            continue
        sid = str(it.get("id") or f"install_{idx + 1}").strip() or f"install_{idx + 1}"
        kind = str(it.get("kind") or "").strip().lower()
        if not kind:
            continue
        out.append(SkillInstallSpec(id=sid, kind=kind, payload=dict(it)))
    return tuple(out)


def parse_runtime_spec(metadata_oclaw: dict[str, Any]) -> SkillRuntimeSpec | None:
    raw = metadata_oclaw.get("runtime")
    if not isinstance(raw, dict):
        return None
    tp = str(raw.get("type") or "").strip().lower()
    if tp not in {"shell", "python", "node", "hook"}:
        return None
    entry = str(raw.get("entry") or "").strip().replace("\\", "/")
    if not entry or entry.startswith("/") or ".." in entry.split("/"):
        return None
    schema = raw.get("schema") if isinstance(raw.get("schema"), dict) else {}
    perms = raw.get("permissions") if isinstance(raw.get("permissions"), dict) else {}
    timeout_s_raw = raw.get("timeout_s")
    timeout_s = float(timeout_s_raw) if isinstance(timeout_s_raw, (int, float)) else None
    max_output_raw = raw.get("max_output_bytes")
    max_output = int(max_output_raw) if isinstance(max_output_raw, int) else None
    return SkillRuntimeSpec(
        type=tp,
        entry=entry,
        schema=dict(schema),
        permissions=dict(perms),
        timeout_s=timeout_s,
        max_output_bytes=max_output,
    )


def parse_skill_frontmatter(*, fm: dict[str, Any], default_name: str) -> ParsedSkillFrontmatter:
    nfm = normalize_frontmatter(fm)
    name = str(nfm.get("name") or default_name).strip() or default_name
    desc = str(nfm.get("description") or "").strip() or f"{name} skill"
    md = nfm.get("metadata")
    md = dict(md) if isinstance(md, dict) else {}
    oc = md.get("oclaw")
    oc = dict(oc) if isinstance(oc, dict) else {}
    return ParsedSkillFrontmatter(
        name=name,
        description=desc,
        user_invocable=bool(nfm.get("user-invocable", True)),
        disable_model_invocation=bool(nfm.get("disable-model-invocation", False)),
        metadata_oclaw=oc,
        install=parse_install_specs(oc),
        runtime=parse_runtime_spec(oc),
    )


__all__ = [
    "SkillInstallSpec",
    "SkillRuntimeSpec",
    "ParsedSkillFrontmatter",
    "normalize_frontmatter",
    "parse_install_specs",
    "parse_runtime_spec",
    "parse_skill_frontmatter",
]

