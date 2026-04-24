from __future__ import annotations

import base64
from typing import Any


def _normalize_attachment_content(content: Any) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, (bytes, bytearray, memoryview)):
        b = bytes(content)
        return base64.b64encode(b).decode("ascii")
    return None


def normalize_rpc_attachments_to_chat_attachments(attachments: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a in attachments or []:
        if not isinstance(a, dict):
            continue
        source = a.get("source")
        source_mime = None
        source_content = None
        if isinstance(source, dict):
            st = source.get("type")
            if isinstance(st, str) and st == "base64":
                media_type = source.get("media_type")
                if isinstance(media_type, str):
                    source_mime = media_type
                source_content = _normalize_attachment_content(source.get("data"))

        item = {
            "type": a.get("type") if isinstance(a.get("type"), str) else None,
            "mimeType": a.get("mimeType") if isinstance(a.get("mimeType"), str) else source_mime,
            "fileName": a.get("fileName") if isinstance(a.get("fileName"), str) else None,
            "content": _normalize_attachment_content(a.get("content")) or source_content,
        }
        if item.get("content"):
            out.append(item)
    return out

