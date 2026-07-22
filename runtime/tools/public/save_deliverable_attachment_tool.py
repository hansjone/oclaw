from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.path_guard import resolve_workspace_path
from svc.files.attachment_assets import AttachmentAssetStore


def _guess_mime(path: Path, override: str) -> str:
    if override:
        return override
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def save_deliverable_attachment_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        attachment_id = str(args.get("attachment_id") or "").strip().lower()
        raw_path = str(args.get("path") or "").strip().strip('"').strip("'")
        display_name = str(args.get("name") or "").strip()
        mime_override = str(args.get("mime") or "").strip()

        if attachment_id:
            store = AttachmentAssetStore()
            meta = store.get_meta(attachment_id)
            if meta is None:
                return {"ok": False, "error": "attachment_not_found", "attachment_id": attachment_id}
            name = display_name or meta.name
            return {
                "ok": True,
                "attachment_id": meta.attachment_id,
                "name": name,
                "mime": mime_override or meta.mime,
                "bytes": meta.bytes,
                "width": meta.width,
                "height": meta.height,
                "deliverable": True,
            }

        if not raw_path:
            return {"ok": False, "error": "path_or_attachment_id_required"}
        try:
            p = resolve_workspace_path(raw_path)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if not p.exists() or not p.is_file():
            return {"ok": False, "error": "file_not_found", "path": str(p)}
        filename = display_name or p.name
        mime = _guess_mime(p, mime_override)
        try:
            data = p.read_bytes()
        except Exception as exc:
            return {"ok": False, "error": "read_failed", "detail": str(exc)}
        meta = AttachmentAssetStore().save_bytes(data, filename=filename, mime=mime)
        return {
            "ok": True,
            "attachment_id": meta.attachment_id,
            "name": meta.name,
            "mime": meta.mime,
            "bytes": meta.bytes,
            "deliverable": True,
        }

    return ToolSpec(
        name="save_deliverable_attachment",
        description=(
            "Mark an attachment for outbound channel delivery (WhatsApp/WeChat). "
            "Required before the user receives any generated file, image, or video in a messaging channel. "
            "Prefer attachment_id for assets already in the store (write_xlsx, cloudflare_image_generate, etc.). "
            "Use path for workspace files (after write_file or run_command). "
            "Generating content alone does not send attachments to the channel."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Workspace file path (relative to workspace root or allowed absolute path).",
                },
                "attachment_id": {
                    "type": "string",
                    "description": (
                        "Existing attachment_id from generation tools "
                        "(write_xlsx, cloudflare_image_generate, image_edit, etc.)."
                    ),
                },
                "name": {
                    "type": "string",
                    "description": "Optional download filename shown to the user.",
                },
                "mime": {
                    "type": "string",
                    "description": "Optional MIME type override.",
                },
            },
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "workspace", "attachment", "channel"}),
        read_only=False,
        risk_level="low",
    )


__all__ = ["save_deliverable_attachment_tool"]
