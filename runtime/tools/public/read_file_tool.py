from __future__ import annotations

import hashlib
from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.path_guard import resolve_workspace_path


def read_file_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path") or "").strip()
        offset = int(args.get("offset") or 1)
        limit = int(args.get("limit") or 400)
        if offset == 0:
            offset = 1
        if limit <= 0:
            limit = 1
        p = resolve_workspace_path(path)
        if not p.exists() or not p.is_file():
            return {"ok": False, "error": "file_not_found", "path": str(p)}
        text = p.read_text(encoding="utf-8", errors="replace").splitlines()
        if offset < 0:
            start = max(0, len(text) + offset)
        else:
            start = max(0, offset - 1)
        end = min(len(text), start + min(limit, 2000))
        out_lines = [f"{i + 1}|{text[i]}" for i in range(start, end)]
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        return {
            "ok": True,
            "path": str(p),
            "start_line": start + 1,
            "end_line": end,
            "total_lines": len(text),
            "sha256": sha,
            "content": "\n".join(out_lines),
        }

    return ToolSpec(
        name="read_file",
        description="Read a text file from the workspace with line numbers.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path, relative to workspace root."},
                "offset": {"type": "integer", "description": "1-indexed start line; negative counts from end.", "default": 1},
                "limit": {"type": "integer", "description": "Max lines to return (capped).", "default": 400},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "workspace"}),
        read_only=True,
        risk_level="low",
    )


__all__ = ["read_file_tool"]
