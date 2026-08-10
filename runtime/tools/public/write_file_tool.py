from __future__ import annotations

from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.path_guard import resolve_workspace_path


def _resolve_write_path(args: dict[str, Any]) -> str:
    for key in ("path", "file", "filename", "file_path", "filepath", "name"):
        raw = str(args.get(key) or "").strip().strip('"').strip("'")
        if raw:
            return raw
    return ""


def write_file_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        raw = _resolve_write_path(args)
        if not raw:
            return {
                "ok": False,
                "error": "path_required",
                "hint": "Pass path (or file/filename) relative to workspace root.",
                "example": {"path": "tmp/notes.txt", "content": "hello", "mode": "overwrite"},
            }
        content = args.get("content")
        if content is None:
            content = args.get("text")
        if content is None:
            content = args.get("body")
        content_s = "" if content is None else str(content)
        mode = str(args.get("mode") or "overwrite").strip().lower()
        try:
            p = resolve_workspace_path(raw)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        p.parent.mkdir(parents=True, exist_ok=True)
        if mode not in ("overwrite", "append"):
            return {"ok": False, "error": "invalid_mode", "allowed": ["overwrite", "append"]}
        if mode == "append":
            p.write_text(p.read_text(encoding="utf-8", errors="replace") + content_s, encoding="utf-8")
        else:
            p.write_text(content_s, encoding="utf-8")
        return {"ok": True, "path": str(p), "bytes": p.stat().st_size}

    return ToolSpec(
        name="write_file",
        description=(
            "Write text content to a workspace file (overwrite or append). "
            "Path aliases: file, filename, file_path."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path, relative to workspace root."},
                "file": {"type": "string", "description": "Alias for path."},
                "filename": {"type": "string", "description": "Alias for path."},
                "file_path": {"type": "string", "description": "Alias for path."},
                "filepath": {"type": "string", "description": "Alias for path."},
                "name": {"type": "string", "description": "Alias for path (when it looks like a relative file path)."},
                "content": {"type": "string", "description": "Full text content to write."},
                "text": {"type": "string", "description": "Alias for content."},
                "body": {"type": "string", "description": "Alias for content."},
                "mode": {"type": "string", "enum": ["overwrite", "append"], "default": "overwrite"},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "workspace", "write"}),
        risk_level="high",
        read_only=False,
    )


__all__ = ["write_file_tool"]
