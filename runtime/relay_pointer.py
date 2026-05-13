from __future__ import annotations

import base64
import binascii
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.types import SharedAttachmentManifest, SharedFilePointer

_SAFE_FILE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SAFE_SCOPE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SAFE_FILE_ID = re.compile(r"^[a-f0-9]{8,64}$")


class RelayPointerError(ValueError):
    """Raised when relay pointer payload or path is invalid."""


@dataclass(frozen=True)
class RelayPointerLimits:
    max_files: int = 32
    max_file_bytes: int = 8 * 1024 * 1024
    max_total_bytes: int = 64 * 1024 * 1024


def validate_file_name(name: str) -> str:
    s = str(name or "").strip()
    if not s:
        raise RelayPointerError("file_name_required")
    if s in {".", ".."}:
        raise RelayPointerError("file_name_invalid")
    if "/" in s or "\\" in s:
        raise RelayPointerError("file_name_invalid")
    if not _SAFE_FILE_NAME.match(s):
        raise RelayPointerError("file_name_invalid")
    return s


def normalize_rel_path(rel_path: str) -> str:
    raw = str(rel_path or "").strip()
    if not raw:
        raise RelayPointerError("rel_path_required")
    p = Path(raw.replace("\\", "/"))
    if p.is_absolute():
        raise RelayPointerError("rel_path_absolute")
    parts = [x for x in p.parts if str(x or "").strip()]
    if not parts:
        raise RelayPointerError("rel_path_required")
    if any(x in {".", ".."} for x in parts):
        raise RelayPointerError("rel_path_traversal")
    return "/".join(parts)


def safe_join_under_root(root: Path, rel_path: str) -> Path:
    root_resolved = Path(root).resolve()
    normalized = normalize_rel_path(rel_path)
    out = (root_resolved / normalized).resolve()
    try:
        out.relative_to(root_resolved)
    except Exception as exc:
        raise RelayPointerError("path_outside_root") from exc
    return out


def decode_base64_payload(payload: str, *, max_bytes: int) -> bytes:
    raw = str(payload or "").strip()
    if not raw:
        raise RelayPointerError("payload_required")
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RelayPointerError("payload_base64_invalid") from exc
    if len(data) > int(max_bytes):
        raise RelayPointerError("payload_too_large")
    return data


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_pointer_uri(scope_id: str, file_id: str) -> str:
    s = str(scope_id or "").strip()
    f = str(file_id or "").strip().lower()
    if not _SAFE_SCOPE_ID.match(s):
        raise RelayPointerError("scope_id_invalid")
    if not _SAFE_FILE_ID.match(f):
        raise RelayPointerError("file_id_invalid")
    return f"relay://attachments/{s}/{f}"


def parse_pointer_uri(pointer_uri: str) -> tuple[str, str]:
    s = str(pointer_uri or "").strip()
    prefix = "relay://attachments/"
    if not s.startswith(prefix):
        raise RelayPointerError("pointer_uri_invalid")
    rest = s[len(prefix) :]
    chunks = rest.split("/")
    if len(chunks) != 2:
        raise RelayPointerError("pointer_uri_invalid")
    scope_id, file_id = chunks[0].strip(), chunks[1].strip().lower()
    if not _SAFE_SCOPE_ID.match(scope_id):
        raise RelayPointerError("scope_id_invalid")
    if not _SAFE_FILE_ID.match(file_id):
        raise RelayPointerError("file_id_invalid")
    return scope_id, file_id


def build_manifest_from_attachment_refs(
    attachments: list[dict[str, Any]] | None,
    *,
    scope_id: str,
    source_agent: str,
    created_at: str = "",
    ttl_policy: str = "turn",
) -> SharedAttachmentManifest:
    items = attachments if isinstance(attachments, list) else []
    pointers: list[SharedFilePointer] = []
    total = 0
    for a in items:
        if not isinstance(a, dict):
            continue
        aid = str(a.get("attachment_id") or "").strip().lower()
        if not aid:
            continue
        try:
            uri = build_pointer_uri(scope_id, aid)
        except RelayPointerError:
            continue
        b = int(a.get("bytes") or 0)
        total += max(0, b)
        rel = str(a.get("rel_path") or f"attachments/{aid}")
        pointers.append(
            SharedFilePointer(
                schema_version="v1",
                pointer_uri=uri,
                rel_path=rel,
                mime_type=str(a.get("mime") or ""),
                bytes=max(0, b),
                sha256=str(a.get("sha256") or aid),
                source_agent=str(source_agent or ""),
                created_at=str(created_at or ""),
                ttl_policy=str(ttl_policy or "turn"),
                extra={
                    "attachment_id": aid,
                    "name": str(a.get("name") or ""),
                },
            )
        )
    return SharedAttachmentManifest(
        scope_id=str(scope_id or ""),
        count=len(pointers),
        total_bytes=total,
        pointers=tuple(pointers),
    )


def validate_relay_share_envelope(raw: dict[str, Any] | None) -> tuple[bool, str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return (False, "relay_envelope_invalid", {})
    env = dict(raw)
    schema = str(env.get("schema_version") or "").strip().lower()
    if schema != "v1":
        return (False, "relay_envelope_unsupported_version", {})
    attachments = env.get("attachments")
    if not isinstance(attachments, dict):
        return (False, "relay_envelope_invalid", {})
    manifest = SharedAttachmentManifest.from_dict(attachments)
    return (True, "", {"schema_version": "v1", "attachments": manifest.to_dict()})


def summarize_relay_ttl(relay_envelope: dict[str, Any] | None) -> dict[str, int]:
    out = {"total": 0, "turn": 0, "session": 0, "keep": 0, "unknown": 0}
    ok, _err, norm = validate_relay_share_envelope(relay_envelope)
    if not ok:
        return out
    ad = norm.get("attachments") if isinstance(norm, dict) else {}
    ps = ad.get("pointers") if isinstance(ad, dict) else []
    for p in ps if isinstance(ps, list) else []:
        if not isinstance(p, dict):
            continue
        out["total"] += 1
        ttl = str(p.get("ttl_policy") or "").strip().lower()
        if ttl in ("turn", "session", "keep"):
            out[ttl] += 1
        else:
            out["unknown"] += 1
    return out


def build_acp_relay_result(
    *,
    parent_run_id: str,
    child_run_id: str,
    relay_envelope: dict[str, Any] | None,
) -> dict[str, Any]:
    ok, err, norm = validate_relay_share_envelope(relay_envelope)
    out: dict[str, Any] = {
        "acp_parent_run_id": str(parent_run_id or ""),
        "acp_child_run_id": str(child_run_id or ""),
        "relay_ok": bool(ok),
        "relay_error_code": str(err or ""),
        "relay_share_envelope": norm if ok else {},
    }
    ad = norm.get("attachments") if isinstance(norm, dict) else {}
    ps = ad.get("pointers") if isinstance(ad, dict) else []
    out["relay_pointer_count"] = len(ps) if isinstance(ps, list) else 0
    return out


__all__ = [
    "RelayPointerError",
    "RelayPointerLimits",
    "validate_file_name",
    "normalize_rel_path",
    "safe_join_under_root",
    "decode_base64_payload",
    "sha256_hex",
    "build_pointer_uri",
    "parse_pointer_uri",
    "build_manifest_from_attachment_refs",
    "validate_relay_share_envelope",
    "summarize_relay_ttl",
    "build_acp_relay_result",
]
