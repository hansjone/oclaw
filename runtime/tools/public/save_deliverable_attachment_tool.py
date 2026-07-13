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
        raw = str(args.get("path") or "").strip().strip('"').strip("'")
        if not raw:
            return {"ok": False, "error": "path_required"}
        display_name = str(args.get("name") or "").strip()
        mime_override = str(args.get("mime") or "").strip()
        try:
            p = resolve_workspace_path(raw)
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
            "Register a workspace file for outbound channel delivery (WhatsApp/WeChat). "
            "Call this after generating a file with write_file or run_command when the user should receive it as an attachment. "
            "write_file alone does not send files to messaging channels."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Workspace file path (relative to workspace root or allowed absolute path).",
                },
                "name": {
                    "type": "string",
                    "description": "Optional download filename shown to the user.",
                },
                "mime": {
                    "type": "string",
                    "description": "Optional MIME type override (e.g. application/vnd.openxmlformats-officedocument.spreadsheetml.sheet).",
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "workspace", "attachment", "channel"}),
        read_only=False,
        risk_level="low",
    )


__all__ = ["save_deliverable_attachment_tool"]
