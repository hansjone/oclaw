from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HookInstallSpec:
    kind: str
    id: str | None = None
    label: str | None = None
    package: str | None = None
    repository: str | None = None
    bins: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind}
        if self.id:
            out["id"] = self.id
        if self.label:
            out["label"] = self.label
        if self.package:
            out["package"] = self.package
        if self.repository:
            out["repository"] = self.repository
        if self.bins:
            out["bins"] = list(self.bins)
        return out


@dataclass(frozen=True)
class HookRequiresSpec:
    bins: tuple[str, ...] = ()
    any_bins: tuple[str, ...] = ()
    env: tuple[str, ...] = ()
    config: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.bins:
            out["bins"] = list(self.bins)
        if self.any_bins:
            out["anyBins"] = list(self.any_bins)
        if self.env:
            out["env"] = list(self.env)
        if self.config:
            out["config"] = list(self.config)
        return out


@dataclass(frozen=True)
class HookMetadataSpec:
    events: tuple[str, ...] = ()
    always: bool | None = None
    emoji: str | None = None
    homepage: str | None = None
    hook_key: str | None = None
    export: str | None = None
    os: tuple[str, ...] = ()
    requires: HookRequiresSpec | None = None
    install: tuple[HookInstallSpec, ...] = ()
    hook_mode: str | None = None
    node_script: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"events": list(self.events)}
        if self.always is not None:
            out["always"] = bool(self.always)
        if self.emoji:
            out["emoji"] = self.emoji
        if self.homepage:
            out["homepage"] = self.homepage
        if self.hook_key:
            out["hookKey"] = self.hook_key
        if self.export:
            out["export"] = self.export
        if self.os:
            out["os"] = list(self.os)
        if self.requires:
            req = self.requires.as_dict()
            if req:
                out["requires"] = req
        if self.install:
            out["install"] = [row.as_dict() for row in self.install]
        if self.hook_mode is not None:
            out["hookMode"] = str(self.hook_mode)
        if self.node_script is not None:
            out["nodeScript"] = bool(self.node_script)
        return out


@dataclass(frozen=True)
class ParsedHookManifest:
    name: str
    description: str
    invocation_enabled: bool
    metadata: HookMetadataSpec = field(default_factory=HookMetadataSpec)


def _read_str(value: Any) -> str | None:
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    return None


def _normalize_str_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    out: list[str] = []
    for row in value:
        s = _read_str(row)
        if s:
            out.append(s)
    return tuple(out)


def _parse_install_spec(row: Any) -> HookInstallSpec | None:
    if not isinstance(row, dict):
        return None
    kind = (_read_str(row.get("kind")) or "").lower()
    if kind not in {"bundled", "npm", "git"}:
        return None
    return HookInstallSpec(
        kind=kind,
        id=_read_str(row.get("id")),
        label=_read_str(row.get("label")),
        package=_read_str(row.get("package")),
        repository=_read_str(row.get("repository")),
        bins=_normalize_str_list(row.get("bins")),
    )


def _resolve_raw_oclaw_metadata(frontmatter: dict[str, Any]) -> dict[str, Any]:
    meta = frontmatter.get("metadata")
    if isinstance(meta, str):
        try:
            parsed = json.loads(meta)
            meta = parsed if isinstance(parsed, dict) else None
        except Exception:
            meta = None
    if not isinstance(meta, dict):
        return {}
    oc = meta.get("oclaw")
    return oc if isinstance(oc, dict) else {}


def parse_hook_manifest(*, frontmatter: dict[str, Any], default_name: str) -> ParsedHookManifest:
    name = _read_str(frontmatter.get("name")) or default_name
    description = _read_str(frontmatter.get("description")) or ""
    enabled_raw = frontmatter.get("enabled")
    invocation_enabled = bool(enabled_raw) if isinstance(enabled_raw, bool) else True

    oc = _resolve_raw_oclaw_metadata(frontmatter)
    requires_obj = oc.get("requires") if isinstance(oc.get("requires"), dict) else {}
    requires = HookRequiresSpec(
        bins=_normalize_str_list(requires_obj.get("bins")),
        any_bins=_normalize_str_list(requires_obj.get("anyBins")),
        env=_normalize_str_list(requires_obj.get("env")),
        config=_normalize_str_list(requires_obj.get("config")),
    )
    install_rows: list[HookInstallSpec] = []
    if isinstance(oc.get("install"), list):
        for row in oc["install"]:
            parsed = _parse_install_spec(row)
            if parsed:
                install_rows.append(parsed)

    node_script: bool | None
    if "nodeScript" in oc:
        node_script = bool(oc.get("nodeScript"))
    else:
        node_script = None

    metadata = HookMetadataSpec(
        events=_normalize_str_list(oc.get("events")),
        always=bool(oc["always"]) if isinstance(oc.get("always"), bool) else None,
        emoji=_read_str(oc.get("emoji")),
        homepage=_read_str(oc.get("homepage")),
        hook_key=_read_str(oc.get("hookKey")),
        export=_read_str(oc.get("export")),
        os=_normalize_str_list(oc.get("os")),
        requires=requires if requires.as_dict() else None,
        install=tuple(install_rows),
        hook_mode=_read_str(oc.get("hookMode")),
        node_script=node_script,
    )
    return ParsedHookManifest(
        name=name,
        description=description,
        invocation_enabled=invocation_enabled,
        metadata=metadata,
    )

