from __future__ import annotations

from typing import Any

from runtime.tools.base import ToolSpec
from svc.persistence.assistant_store import get_assistant_store


def index_workspace_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        max_files = int(args.get("max_files") or 120)
        try:
            from runtime.tools.workspace_indexer import index_workspace

            store = get_assistant_store()
            st = index_workspace(store, max_files=max(1, min(max_files, 800)))
            return {"ok": True, "files_seen": st.files_seen, "chunks_upserted": st.chunks_upserted, "embeddings_upserted": st.embeddings_upserted}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="index_workspace",
        description="Index workspace files into vector knowledge base for RAG.",
        parameters={
            "type": "object",
            "properties": {"max_files": {"type": "integer", "default": 120, "description": "Max files to index."}},
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"public", "rag"}),
        risk_level="high",
        read_only=False,
    )


__all__ = ["index_workspace_tool"]
