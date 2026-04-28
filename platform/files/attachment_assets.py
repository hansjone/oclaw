from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from oclaw.platform.config.paths import attachments_dir
_META_SUFFIX: Final[str] = ".meta.json"
_ATTACHMENT_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")


def _utc_ts() -> int:
    return int(time.time())


def _safe_rel_name(name: str) -> str:
    # keep it simple: drop path parts, trim, and avoid empty
    raw = (name or "").replace("\\", "/").split("/")[-1].strip()
    return raw or "image"


def _ext_from_mime(mime: str | None) -> str:
    m = (mime or "").strip().lower()
    if m == "image/png":
        return ".png"
    if m in ("image/jpg", "image/jpeg"):
        return ".jpg"
    if m == "image/webp":
        return ".webp"
    if m == "image/gif":
        return ".gif"
    return ""


def _guess_mime_from_ext(ext: str) -> str:
    e = (ext or "").lower().lstrip(".")
    if e == "png":
        return "image/png"
    if e in ("jpg", "jpeg"):
        return "image/jpeg"
    if e == "webp":
        return "image/webp"
    if e == "gif":
        return "image/gif"
    return "application/octet-stream"


@dataclass(frozen=True)
class AttachmentMeta:
    attachment_id: str
    name: str
    mime: str
    bytes: int
    created_at: int
    last_access: int
    width: int | None = None
    height: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "attachment_id": self.attachment_id,
            "name": self.name,
            "mime": self.mime,
            "bytes": int(self.bytes),
            "created_at": int(self.created_at),
            "last_access": int(self.last_access),
        }
        if self.width is not None:
            d["width"] = int(self.width)
        if self.height is not None:
            d["height"] = int(self.height)
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "AttachmentMeta":
        return AttachmentMeta(
            attachment_id=str(d.get("attachment_id") or ""),
            name=str(d.get("name") or ""),
            mime=str(d.get("mime") or "application/octet-stream"),
            bytes=int(d.get("bytes") or 0),
            created_at=int(d.get("created_at") or 0),
            last_access=int(d.get("last_access") or 0),
            width=int(d["width"]) if d.get("width") is not None else None,
            height=int(d["height"]) if d.get("height") is not None else None,
        )


class AttachmentAssetStore:
    """Disk-backed attachment store (project-local by default)."""

    def __init__(self, root_dir: str | Path | None = None):
        self.root = Path(root_dir) if root_dir is not None else attachments_dir()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_attachment_id(attachment_id: str) -> str:
        aid = str(attachment_id or "").strip().lower()
        if not _ATTACHMENT_ID_RE.fullmatch(aid):
            raise ValueError("attachment_id_invalid")
        return aid

    def _data_path(self, attachment_id: str, *, ext: str) -> Path:
        # bucket to avoid huge single dir
        aid = self._normalize_attachment_id(attachment_id)
        p1, p2 = (aid[:2] or "xx"), (aid[2:4] or "yy")
        d = self.root / p1 / p2
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{aid}{ext}"

    def _meta_path(self, attachment_id: str) -> Path:
        aid = self._normalize_attachment_id(attachment_id)
        p1, p2 = (aid[:2] or "xx"), (aid[2:4] or "yy")
        d = self.root / p1 / p2
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{aid}{_META_SUFFIX}"

    def save_bytes(
        self,
        data: bytes,
        *,
        filename: str,
        mime: str | None,
        width: int | None = None,
        height: int | None = None,
    ) -> AttachmentMeta:
        blob = bytes(data or b"")
        h = hashlib.sha256(blob).hexdigest()
        ext = _ext_from_mime(mime) or (("." + filename.split(".")[-1].lower()) if "." in filename else "")
        ext = ext if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif") else _ext_from_mime(mime) or ""
        data_path = self._data_path(h, ext=ext)
        meta_path = self._meta_path(h)

        now = _utc_ts()
        if not data_path.exists():
            tmp = str(data_path) + ".tmp"
            with open(tmp, "wb") as f:
                f.write(blob)
            os.replace(tmp, data_path)

        meta = AttachmentMeta(
            attachment_id=h,
            name=_safe_rel_name(filename),
            mime=(mime or _guess_mime_from_ext(ext)).strip() or _guess_mime_from_ext(ext),
            bytes=len(blob),
            created_at=now,
            last_access=now,
            width=width,
            height=height,
        )
        # best-effort: keep existing created_at if present
        if meta_path.exists():
            try:
                prev = json.loads(meta_path.read_text("utf-8"))
                if isinstance(prev, dict) and prev.get("created_at"):
                    meta = AttachmentMeta(
                        **{**meta.to_dict(), "created_at": int(prev.get("created_at") or now)}  # type: ignore[arg-type]
                    )
            except Exception:
                pass
        meta_path.write_text(json.dumps(meta.to_dict(), ensure_ascii=False), encoding="utf-8")
        return meta

    def get_meta(self, attachment_id: str) -> Optional[AttachmentMeta]:
        try:
            mp = self._meta_path(attachment_id)
        except Exception:
            return None
        if not mp.exists():
            return None
        try:
            obj = json.loads(mp.read_text("utf-8"))
            if not isinstance(obj, dict):
                return None
            return AttachmentMeta.from_dict(obj)
        except Exception:
            return None

    def touch(self, attachment_id: str) -> None:
        try:
            mp = self._meta_path(attachment_id)
        except Exception:
            return
        if not mp.exists():
            return
        try:
            obj = json.loads(mp.read_text("utf-8"))
            if not isinstance(obj, dict):
                return
            obj["last_access"] = _utc_ts()
            mp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        except Exception:
            return

    def load_bytes(self, attachment_id: str) -> tuple[bytes, Optional[AttachmentMeta]]:
        try:
            aid = self._normalize_attachment_id(attachment_id)
        except Exception:
            return b"", None
        meta = self.get_meta(aid)
        # try find data file by scanning common extensions
        exts = (".png", ".jpg", ".jpeg", ".webp", ".gif", "")
        data_path = None
        for ext in exts:
            p = self._data_path(aid, ext=ext)
            if p.exists():
                data_path = p
                break
        if data_path is None:
            return b"", meta
        try:
            blob = data_path.read_bytes()
        except Exception:
            return b"", meta
        self.touch(aid)
        return blob, meta

    def get_local_path(self, attachment_id: str) -> Path | None:
        try:
            aid = self._normalize_attachment_id(attachment_id)
        except Exception:
            return None
        exts = (".png", ".jpg", ".jpeg", ".webp", ".gif", "")
        for ext in exts:
            p = self._data_path(aid, ext=ext)
            if p.exists():
                self.touch(aid)
                return p
        return None

    def inspect_asset(self, attachment_id: str) -> dict[str, Any]:
        meta = self.get_meta(attachment_id)
        p = self.get_local_path(attachment_id)
        if meta is None and p is None:
            return {"state": "missing", "attachment_id": attachment_id}
        if meta is not None and p is None:
            return {
                "state": "meta_exists_blob_missing",
                "attachment_id": attachment_id,
                "meta": meta.to_dict(),
            }
        return {
            "state": "ok",
            "attachment_id": attachment_id,
            "meta": meta.to_dict() if meta else None,
            "path": str(p) if p is not None else "",
        }

    def get_render_cache_key(self, attachment_id: str, *, mime_hint: str | None = None) -> tuple[str, str, int, int]:
        meta = self.get_meta(attachment_id)
        return (
            str(attachment_id or "").strip(),
            str(mime_hint or (meta.mime if meta else "") or "image/jpeg"),
            int(meta.bytes if meta else 0),
            int(meta.created_at if meta else 0),
        )

    def gc(self, *, ttl_days: int = 7) -> dict[str, Any]:
        ttl_sec = max(1, int(ttl_days)) * 86400
        now = _utc_ts()
        removed = 0
        kept = 0

        if not self.root.exists():
            return {"ok": True, "removed": 0, "kept": 0}

        for mp in self.root.rglob(f"*{_META_SUFFIX}"):
            try:
                obj = json.loads(mp.read_text("utf-8"))
                if not isinstance(obj, dict):
                    continue
                last_access = int(obj.get("last_access") or obj.get("created_at") or 0)
                aid = str(obj.get("attachment_id") or mp.name.replace(_META_SUFFIX, ""))
            except Exception:
                continue
            if last_access and (now - last_access) <= ttl_sec:
                kept += 1
                continue

            # delete meta + possible data files
            try:
                mp.unlink(missing_ok=True)  # py3.8+; on 3.14 ok
            except Exception:
                pass
            for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ""):
                try:
                    self._data_path(aid, ext=ext).unlink(missing_ok=True)
                except Exception:
                    pass
            removed += 1

        return {"ok": True, "removed": removed, "kept": kept}


_LAST_GC_TS: int = 0


def gc_if_due(*, ttl_days: int = 7, min_interval_sec: int = 3600, root_dir: str | Path | None = None) -> None:
    """Best-effort throttled GC to be called in UI loop."""
    global _LAST_GC_TS
    now = _utc_ts()
    if _LAST_GC_TS and (now - _LAST_GC_TS) < max(10, int(min_interval_sec)):
        return
    _LAST_GC_TS = now
    try:
        AttachmentAssetStore(root_dir).gc(ttl_days=ttl_days)
    except Exception:
        return


def image_ref_to_data_url(att: dict[str, Any], *, root_dir: str | Path | None = None) -> tuple[str, str]:
    """Helper for UI: convert image_ref to (mime, data_url_base64_payload)."""
    aid = str(att.get("attachment_id") or "").strip()
    if not aid:
        return "image/jpeg", ""
    store = AttachmentAssetStore(root_dir)
    blob, meta = store.load_bytes(aid)
    mime = str(att.get("mime") or (meta.mime if meta else "image/jpeg") or "image/jpeg")
    if not blob:
        return mime, ""
    b64 = base64.b64encode(blob).decode("ascii")
    return mime, b64


def attachment_id_to_data_url(
    attachment_id: str,
    *,
    mime: str | None = None,
    root_dir: str | Path | None = None,
) -> str:
    """Convert stored attachment bytes into data URL form."""
    aid = str(attachment_id or "").strip()
    if not aid:
        return ""
    store = AttachmentAssetStore(root_dir)
    blob, meta = store.load_bytes(aid)
    if not blob:
        return ""
    resolved_mime = str(mime or (meta.mime if meta else "") or "image/jpeg")
    b64 = base64.b64encode(blob).decode("ascii")
    return f"data:{resolved_mime};base64,{b64}"


__all__ = [
    "AttachmentAssetStore",
    "AttachmentMeta",
    "attachment_id_to_data_url",
    "gc_if_due",
    "image_ref_to_data_url",
]

