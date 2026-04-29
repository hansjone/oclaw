from __future__ import annotations

import re
from typing import Any
from pathlib import Path

from oclaw.platform.files.attachment_assets import AttachmentAssetStore
from oclaw.runtime.tools.base import ToolSpec

_ATTACHMENT_ID_RE = re.compile(r"^[a-f0-9]{64}$")


def attachment_local_url_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        attachment_id = str(args.get("attachment_id") or "").strip().lower()
        if not attachment_id:
            return {"ok": False, "error": "attachment_id_required"}
        if not _ATTACHMENT_ID_RE.fullmatch(attachment_id):
            return {"ok": False, "error": "attachment_id_invalid"}

        store = AttachmentAssetStore()
        meta = store.get_meta(attachment_id)
        local_path = store.get_local_path(attachment_id)
        local_path_text = str(local_path) if local_path else ""
        file_url = Path(local_path).resolve().as_uri() if local_path else ""

        return {
            "ok": True,
            "attachment_id": attachment_id,
            "exists": bool(meta or local_path),
            # For direct rendering in desktop/electron contexts, prefer file URL first.
            "preferred_url": file_url or local_path_text,
            "mime": str(getattr(meta, "mime", "") or ""),
            "name": str(getattr(meta, "name", "") or ""),
            "bytes": int(getattr(meta, "bytes", 0) or 0),
            "local_path": local_path_text,
            "file_url": file_url,
        }

    return ToolSpec(
        name="attachment_local_url",
        description="Resolve attachment_id to local download URL under this oclaw gateway.",
        parameters={
            "type": "object",
            "properties": {
                "attachment_id": {"type": "string", "description": "Stored attachment id."},
            },
            "required": ["attachment_id"],
            "additionalProperties": False,
        },
        handler=_handler,
        read_only=True,
        tags=frozenset({"attachment", "url", "read"}),
        risk_level="low",
        timeout_s=2.0,
    )


__all__ = ["attachment_local_url_tool"]
