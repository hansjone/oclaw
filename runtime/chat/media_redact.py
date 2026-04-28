"""Strip/ingest embedded binary payloads from tool/MCP-shaped JSON.

Persistence is untouched; callers use copies when building model context."""

from __future__ import annotations

import base64
import os
from typing import Any
from oclaw.platform.files.attachment_assets import AttachmentAssetStore

_IMAGE_CONTENT_TYPES = frozenset({"image", "input_image"})
_BASE64_PAYLOAD_KEYS = ("data", "image_base64", "base64", "content_base64", "body_base64")
# Below this length we keep values (tiny icons / markers).
_MIN_B64_CHARS = 200
_DEFAULT_MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024


def redact_embedded_image_blobs(obj: Any) -> Any:
    """Deep-copy-ish transform: replace large base64 payloads with metadata placeholders."""
    if isinstance(obj, dict):
        return _redact_dict(obj)
    if isinstance(obj, list):
        return [redact_embedded_image_blobs(x) for x in obj]
    return obj


def _looks_like_large_payload(s: str) -> bool:
    t = str(s or "").strip()
    if len(t) < _MIN_B64_CHARS:
        return False
    allowed = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r-_")
    if not t[: min(512, len(t))]:
        return False
    noise = sum(1 for ch in t[: min(2000, len(t))] if ch not in allowed)
    return noise <= max(2, len(t[: min(2000, len(t))]) // 200)


def _redact_dict(d: dict[str, Any]) -> dict[str, Any]:
    typ = str(d.get("type") or "").strip().lower()
    payload_keys = [k for k in _BASE64_PAYLOAD_KEYS if isinstance(d.get(k), str) and _looks_like_large_payload(str(d.get(k) or ""))]
    if payload_keys:
        plen = max(len(str(d.get(k) or "")) for k in payload_keys)
        dup: dict[str, Any] = {}
        for k, v in d.items():
            if k in payload_keys:
                continue
            if isinstance(v, dict):
                dup[k] = _redact_dict(v)
            elif isinstance(v, list):
                dup[k] = [redact_embedded_image_blobs(x) for x in v]
            else:
                dup[k] = v
        is_image = typ in _IMAGE_CONTENT_TYPES
        dup["_image_payload_redacted" if is_image else "_binary_payload_redacted"] = True
        dup["_redacted_payload_chars"] = int(plen)
        dup["_redacted_payload_keys"] = list(payload_keys)
        return dup

    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = _redact_dict(v)
        elif isinstance(v, list):
            out[k] = [redact_embedded_image_blobs(x) for x in v]
        else:
            out[k] = v
    return out


def ingest_embedded_image_blobs_as_refs(
    obj: Any,
    *,
    root_dir: str | None = None,
    filename_prefix: str = "tool-image",
) -> tuple[Any, list[dict[str, Any]]]:
    """Persist nested base64 blobs and replace them with attachment refs.

    Returns transformed object and newly created attachment refs.
    """
    store = AttachmentAssetStore(root_dir=root_dir) if root_dir else AttachmentAssetStore()
    refs: list[dict[str, Any]] = []

    def _ingest(node: Any, idx_seed: list[int]) -> Any:
        if isinstance(node, list):
            return [_ingest(x, idx_seed) for x in node]
        if not isinstance(node, dict):
            return node
        typ = str(node.get("type") or "").strip().lower()
        raw = _pick_base64_payload(node)
        if raw:
            blob = _decode_image_bytes(raw)
            if blob:
                max_bytes = _max_attachment_bytes()
                if max_bytes > 0 and len(blob) > max_bytes:
                    redacted = _redact_dict(node)
                    redacted["type"] = _ref_type_for_mime(
                        str(node.get("mime") or node.get("mime_type") or "application/octet-stream"),
                        typ,
                    )
                    redacted["error"] = "attachment_too_large"
                    redacted["max_bytes"] = int(max_bytes)
                    redacted["actual_bytes"] = int(len(blob))
                    redacted.setdefault("name", str(node.get("name") or "attachment"))
                    redacted.setdefault("mime", str(node.get("mime") or node.get("mime_type") or "application/octet-stream"))
                    return redacted
                idx_seed[0] += 1
                mime = str(node.get("mime") or node.get("mime_type") or "image/png").strip() or "image/png"
                ext = _filename_ext_for_mime(mime)
                name = str(node.get("name") or f"{filename_prefix}-{idx_seed[0]}{ext}").strip()
                meta = store.save_bytes(
                    blob,
                    filename=name,
                    mime=mime,
                    width=_safe_int(node.get("width")),
                    height=_safe_int(node.get("height")),
                )
                ref_type = _ref_type_for_mime(mime, typ)
                ref = {
                    "type": ref_type,
                    "attachment_id": meta.attachment_id,
                    "name": meta.name,
                    "mime": meta.mime,
                    "bytes": meta.bytes,
                    "width": meta.width,
                    "height": meta.height,
                }
                refs.append(ref)
                return ref
            redacted = _redact_dict(node)
            redacted["type"] = _ref_type_for_mime(
                str(node.get("mime") or node.get("mime_type") or "application/octet-stream"),
                typ,
            )
            redacted.setdefault("name", str(node.get("name") or "attachment"))
            redacted.setdefault("mime", str(node.get("mime") or node.get("mime_type") or "application/octet-stream"))
            return redacted
        out: dict[str, Any] = {}
        for k, v in node.items():
            out[k] = _ingest(v, idx_seed)
        return out

    transformed = _ingest(obj, [0])
    uniq: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in refs:
        aid = str(r.get("attachment_id") or "").strip()
        if not aid or aid in seen:
            continue
        seen.add(aid)
        uniq.append(r)
    return transformed, uniq


def _decode_image_bytes(raw: Any) -> bytes:
    s = str(raw or "").strip()
    if not s:
        return b""
    if s.startswith("data:") and ";base64," in s:
        s = s.split(";base64,", 1)[1]
    try:
        return base64.b64decode(s.encode("ascii"), validate=False)
    except Exception:
        return b""


def _pick_base64_payload(node: dict[str, Any]) -> str:
    for k in _BASE64_PAYLOAD_KEYS:
        v = node.get(k)
        if isinstance(v, str) and str(v).strip():
            return v
    return ""


def _ref_type_for_mime(mime: str, typ: str = "") -> str:
    m = str(mime or "").strip().lower()
    t = str(typ or "").strip().lower()
    if t in _IMAGE_CONTENT_TYPES or m.startswith("image/"):
        return "image_ref"
    if m.startswith("video/"):
        return "video_ref"
    if m.startswith("text/"):
        return "text_ref"
    return "binary_ref"


def _filename_ext_for_mime(mime: str) -> str:
    m = str(mime or "").strip().lower()
    if m == "image/png":
        return ".png"
    if m in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if m == "image/webp":
        return ".webp"
    if m == "image/gif":
        return ".gif"
    if m == "video/mp4":
        return ".mp4"
    if m == "text/plain":
        return ".txt"
    return ".bin"


def _safe_int(raw: Any) -> int | None:
    try:
        if raw is None:
            return None
        return int(raw)
    except Exception:
        return None


def _max_attachment_bytes() -> int:
    raw = str(os.getenv("AIA_MAX_ATTACHMENT_BYTES") or "").strip()
    if raw.isdigit():
        n = int(raw)
        if n <= 0:
            return 0
        return min(n, 500 * 1024 * 1024)
    return _DEFAULT_MAX_ATTACHMENT_BYTES


__all__ = ["redact_embedded_image_blobs", "ingest_embedded_image_blobs_as_refs"]
