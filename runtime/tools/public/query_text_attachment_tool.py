from __future__ import annotations

from typing import Any

from oclaw.platform.files.text_attachment_store import query_text_document
from oclaw.runtime.tools.base import ToolSpec


def query_text_attachment_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        text_id = str(args.get("text_id") or "").strip()
        if not text_id:
            return {"ok": False, "error": "text_id_required"}
        return query_text_document(
            text_id=text_id,
            query=str(args.get("query") or "").strip() or None,
            top_k=int(args.get("top_k") or 5),
            offset=int(args.get("offset") or 0),
        )

    return ToolSpec(
        name="query_text_attachment",
        description="Query long text attachment chunks by text_id with optional keyword search.",
        parameters={
            "type": "object",
            "properties": {
                "text_id": {"type": "string"},
                "query": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 50},
                "offset": {"type": "integer", "minimum": 0},
            },
            "required": ["text_id"],
            "additionalProperties": False,
        },
        handler=handler,
        read_only=True,
    )


__all__ = ["query_text_attachment_tool"]
