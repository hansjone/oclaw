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
        verbose = bool(args.get("verbose"))
        if not attachment_id:
            return {"ok": False, "error": "attachment_id_required"}
        if not _ATTACHMENT_ID_RE.fullmatch(attachment_id):
            return {"ok": False, "error": "attachment_id_invalid"}

        store = AttachmentAssetStore()
        meta = store.get_meta(attachment_id)
        local_path = store.get_local_path(attachment_id)
        local_path_text = str(local_path) if local_path else ""
        file_url = Path(local_path).resolve().as_uri() if local_path else ""

        out = {
            "ok": True,
            "attachment_id": attachment_id,
            "mime": str(getattr(meta, "mime", "") or ""),
            "name": str(getattr(meta, "name", "") or ""),
            "bytes": int(getattr(meta, "bytes", 0) or 0),
            "file_url": file_url,
        }
        if verbose:
            # Keep debug/context fields opt-in to reduce response noise.
            out["exists"] = bool(meta or local_path)
            out["local_path"] = local_path_text
            out["preferred_url"] = file_url or local_path_text
        return out

    return ToolSpec(
        name="attachment_local_url",
        description="Resolve attachment_id to local download URL under this oclaw gateway.",
        parameters={
            "type": "object",
            "properties": {
                "attachment_id": {"type": "string", "description": "Stored attachment id."},
                "verbose": {
                    "type": "boolean",
                    "description": "When true, include extra debug fields (exists/local_path/preferred_url).",
                },
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
