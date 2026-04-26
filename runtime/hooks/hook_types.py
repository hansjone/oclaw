from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

HookSource = Literal["oclaw-bundled", "oclaw-plugin", "oclaw-managed", "oclaw-workspace"]
_HOOK_SOURCES: tuple[HookSource, ...] = (
    "oclaw-bundled",
    "oclaw-plugin",
    "oclaw-managed",
    "oclaw-workspace",
)


class HookEntryDict(TypedDict, total=False):
    hook: dict[str, Any]
    frontmatter: dict[str, Any]
    metadata: dict[str, Any]
    invocation: dict[str, Any]


class HookRemoteEligibility(TypedDict, total=False):
    platforms: list[str]
    hasBin: Any
    hasAnyBin: Any
    note: str


class HookEligibilityContext(TypedDict, total=False):
    remote: HookRemoteEligibility


@dataclass(frozen=True)
class HookRef:
    name: str
    description: str
    source: HookSource
    pluginId: str | None
    filePath: str
    baseDir: str
    handlerPath: str


@dataclass(frozen=True)
class HookInvocation:
    enabled: bool = True


@dataclass(frozen=True)
class HookEntry:
    hook: HookRef
    frontmatter: dict[str, Any]
    metadata: dict[str, Any]
    invocation: HookInvocation

    def as_dict(self) -> dict[str, Any]:
        return {
            "hook": {
                "name": self.hook.name,
                "description": self.hook.description,
                "source": self.hook.source,
                "pluginId": self.hook.pluginId,
                "filePath": self.hook.filePath,
                "baseDir": self.hook.baseDir,
                "handlerPath": self.hook.handlerPath,
            },
            "frontmatter": dict(self.frontmatter),
            "metadata": dict(self.metadata),
            "invocation": {"enabled": bool(self.invocation.enabled)},
        }


def ensure_entry_dict(entry: HookEntry | HookEntryDict) -> dict[str, Any]:
    return entry.as_dict() if isinstance(entry, HookEntry) else dict(entry)


def _normalize_source(value: Any) -> HookSource:
    s = str(value or "").strip()
    if s in _HOOK_SOURCES:
        return s
    return "oclaw-managed"


def ensure_hook_entry(entry: HookEntry | HookEntryDict) -> HookEntry:
    if isinstance(entry, HookEntry):
        return entry
    row = dict(entry or {})
    hook_raw = row.get("hook") if isinstance(row.get("hook"), dict) else {}
    inv_raw = row.get("invocation") if isinstance(row.get("invocation"), dict) else {}
    return HookEntry(
        hook=HookRef(
            name=str(hook_raw.get("name") or ""),
            description=str(hook_raw.get("description") or ""),
            source=_normalize_source(hook_raw.get("source")),
            pluginId=(str(hook_raw.get("pluginId")) if hook_raw.get("pluginId") is not None else None),
            filePath=str(hook_raw.get("filePath") or ""),
            baseDir=str(hook_raw.get("baseDir") or ""),
            handlerPath=str(hook_raw.get("handlerPath") or ""),
        ),
        frontmatter=dict(row.get("frontmatter") or {}),
        metadata=dict(row.get("metadata") or {}),
        invocation=HookInvocation(enabled=bool(inv_raw.get("enabled")) if "enabled" in inv_raw else True),
    )

