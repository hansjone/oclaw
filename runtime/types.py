from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

InteractionMode = Literal["comprehensive", "expert"]
SpecialistId = str

ChannelId = Literal[
    "admin_chat",
    "wecom",
    "feishu",
    "discord",
    "api",
    "eval",
    "specialist",
    "agent_turn",
    "unknown",
]


@dataclass(frozen=True)
class StandardMessage:
    """oclaw-style normalized inbound message for runtime stages."""

    session_id: str
    tenant_id: str
    user_id: str
    role: str
    channel: ChannelId
    text: str
    attachments: list[dict[str, Any]]
    metadata: dict[str, Any]


def normalize_interaction_mode(raw: Any) -> InteractionMode:
    mode = str(raw or "").strip().lower()
    if mode in {"expert", "specialist"}:
        return "expert"
    return "comprehensive"


def normalize_requested_specialist(raw: Any) -> SpecialistId:
    specialist = str(raw or "").strip().lower()
    if specialist == "ops":
        return "ops"
    if specialist == "image":
        return "image"
    if specialist == "memory":
        return "memory"
    return "generalist"


@dataclass(frozen=True)
class OclawSessionContext:
    session_id: str
    tenant_id: str
    user_id: str
    role: str
    channel: ChannelId
    lang: str
    trace_id: str
    parent_span_id: str | None = None


@dataclass(frozen=True)
class OclawMemoryContext:
    short_term: tuple[str, ...] = ()
    semantic_hits: tuple[dict[str, Any], ...] = ()

    @property
    def enabled(self) -> bool:
        return bool(self.short_term or self.semantic_hits)


@dataclass(frozen=True)
class AttemptState:
    attempt_no: int
    status: str
    reason: str = ""
    error_code: str = ""
    tool_trace_count: int = 0
    compact_triggered: bool = False


@dataclass(frozen=True)
class RunState:
    run_id: str
    session_id: str
    status: str
    attempts: tuple[AttemptState, ...] = ()
    compact_count: int = 0
    last_error_code: str = ""
    stop_reason: str = ""


@dataclass(frozen=True)
class SharedFilePointer:
    schema_version: str = "v1"
    pointer_uri: str = ""
    rel_path: str = ""
    mime_type: str = ""
    bytes: int = 0
    sha256: str = ""
    source_agent: str = ""
    created_at: str = ""
    ttl_policy: str = "turn"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": str(self.schema_version or "v1"),
            "pointer_uri": str(self.pointer_uri or ""),
            "rel_path": str(self.rel_path or ""),
            "mime_type": str(self.mime_type or ""),
            "bytes": int(self.bytes or 0),
            "sha256": str(self.sha256 or ""),
            "source_agent": str(self.source_agent or ""),
            "created_at": str(self.created_at or ""),
            "ttl_policy": str(self.ttl_policy or "turn"),
        }
        if isinstance(self.extra, dict):
            for k, v in self.extra.items():
                if str(k or "") not in out:
                    out[str(k)] = v
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "SharedFilePointer":
        d = raw if isinstance(raw, dict) else {}
        known = {
            "schema_version",
            "pointer_uri",
            "rel_path",
            "mime_type",
            "bytes",
            "sha256",
            "source_agent",
            "created_at",
            "ttl_policy",
        }
        extra = {str(k): v for k, v in d.items() if str(k) not in known}
        return cls(
            schema_version=str(d.get("schema_version") or "v1"),
            pointer_uri=str(d.get("pointer_uri") or ""),
            rel_path=str(d.get("rel_path") or ""),
            mime_type=str(d.get("mime_type") or ""),
            bytes=int(d.get("bytes") or 0),
            sha256=str(d.get("sha256") or ""),
            source_agent=str(d.get("source_agent") or ""),
            created_at=str(d.get("created_at") or ""),
            ttl_policy=str(d.get("ttl_policy") or "turn"),
            extra=extra,
        )


@dataclass(frozen=True)
class SharedAttachmentManifest:
    scope_id: str = ""
    count: int = 0
    total_bytes: int = 0
    pointers: tuple[SharedFilePointer, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "scope_id": str(self.scope_id or ""),
            "count": int(self.count or 0),
            "total_bytes": int(self.total_bytes or 0),
            "pointers": [p.to_dict() for p in self.pointers],
        }
        if isinstance(self.extra, dict):
            for k, v in self.extra.items():
                if str(k or "") not in out:
                    out[str(k)] = v
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "SharedAttachmentManifest":
        d = raw if isinstance(raw, dict) else {}
        known = {"scope_id", "count", "total_bytes", "pointers"}
        ptrs_raw = d.get("pointers")
        ptrs = ptrs_raw if isinstance(ptrs_raw, list) else []
        extra = {str(k): v for k, v in d.items() if str(k) not in known}
        return cls(
            scope_id=str(d.get("scope_id") or ""),
            count=int(d.get("count") or 0),
            total_bytes=int(d.get("total_bytes") or 0),
            pointers=tuple(SharedFilePointer.from_dict(x) for x in ptrs if isinstance(x, dict)),
            extra=extra,
        )


@dataclass(frozen=True)
class RelayShareEnvelope:
    schema_version: str = "v1"
    trace_id: str = ""
    run_id: str = ""
    attempt_no: int = 0
    attachments: SharedAttachmentManifest = field(default_factory=SharedAttachmentManifest)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": str(self.schema_version or "v1"),
            "trace_id": str(self.trace_id or ""),
            "run_id": str(self.run_id or ""),
            "attempt_no": int(self.attempt_no or 0),
            "attachments": self.attachments.to_dict(),
        }
        if isinstance(self.extra, dict):
            for k, v in self.extra.items():
                if str(k or "") not in out:
                    out[str(k)] = v
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "RelayShareEnvelope":
        d = raw if isinstance(raw, dict) else {}
        known = {"schema_version", "trace_id", "run_id", "attempt_no", "attachments"}
        extra = {str(k): v for k, v in d.items() if str(k) not in known}
        return cls(
            schema_version=str(d.get("schema_version") or "v1"),
            trace_id=str(d.get("trace_id") or ""),
            run_id=str(d.get("run_id") or ""),
            attempt_no=int(d.get("attempt_no") or 0),
            attachments=SharedAttachmentManifest.from_dict(d.get("attachments") if isinstance(d.get("attachments"), dict) else {}),
            extra=extra,
        )


__all__ = [
    "InteractionMode",
    "SpecialistId",
    "ChannelId",
    "StandardMessage",
    "normalize_interaction_mode",
    "normalize_requested_specialist",
    "OclawSessionContext",
    "OclawMemoryContext",
    "AttemptState",
    "RunState",
    "SharedFilePointer",
    "SharedAttachmentManifest",
    "RelayShareEnvelope",
]
