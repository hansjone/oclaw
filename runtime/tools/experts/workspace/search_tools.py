from __future__ import annotations

import re
from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.experts.workspace.workspace_base import resolve_workspace_path


def grep_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        pattern = str(args.get("pattern") or "").strip()
        file_glob = str(args.get("file_glob") or "**/*").strip() or "**/*"
        max_matches = int(args.get("max_matches") or 200)
        if not pattern:
            return {"ok": False, "error": "pattern_required"}
        root = resolve_workspace_path(".")
        try:
            rx = re.compile(pattern)
        except re.error as e:
            return {"ok": False, "error": "invalid_regex", "detail": str(e)}
        matches: list[dict[str, Any]] = []
        for p in root.glob(file_glob):
            if p.is_dir():
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(text, start=1):
                if rx.search(line):
                    matches.append({"file": str(p.relative_to(root)), "line": i, "text": line[:400]})
                    if len(matches) >= max(1, min(max_matches, 5000)):
                        return {"ok": True, "pattern": pattern, "count": len(matches), "matches": matches}
        return {"ok": True, "pattern": pattern, "count": len(matches), "matches": matches}

    return ToolSpec(
        name="grep",
        description="Search files in the workspace for a regex pattern.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern."},
                "file_glob": {"type": "string", "default": "**/*", "description": "Glob of files to search."},
                "max_matches": {"type": "integer", "default": 200, "description": "Max number of matches."},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"workspace"}),
        read_only=True,
    )


def index_workspace_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        max_files = int(args.get("max_files") or 120)
        try:
            # Lazy import to avoid heavy deps during tool discovery.
            from oclaw.platform.config.paths import db_path
        except Exception:
            pass
        # Indexer uses store passed via closure? ToolSpec doesn't carry store.
        # We index using the global SqliteStore path (same as app runtime).
        try:
            from oclaw.platform.persistence.sqlite_store import SqliteStore
            from oclaw.platform.config.paths import db_path
            from oclaw.runtime.tools.workspace_indexer import index_workspace

            store = SqliteStore(db_path())
            st = index_workspace(store, max_files=max(1, min(max_files, 800)))
            return {"ok": True, "files_seen": st.files_seen, "chunks_upserted": st.chunks_upserted, "embeddings_upserted": st.embeddings_upserted}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="index_workspace",
        description="Index workspace files into the vector knowledge base for RAG (may be slow).",
        parameters={
            "type": "object",
            "properties": {"max_files": {"type": "integer", "default": 120, "description": "Max files to index."}},
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"workspace", "rag"}),
    )


__all__ = ["grep_tool", "index_workspace_tool"]

