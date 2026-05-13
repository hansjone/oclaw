from __future__ import annotations

from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.path_guard import resolve_workspace_path


def write_file_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        raw = str(args.get("path") or "").strip().strip('"').strip("'")
        if not raw:
            return {"ok": False, "error": "path_required"}
        content = str(args.get("content") or "")
        mode = str(args.get("mode") or "overwrite").strip().lower()
        try:
            p = resolve_workspace_path(raw)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        p.parent.mkdir(parents=True, exist_ok=True)
        if mode not in ("overwrite", "append"):
            return {"ok": False, "error": "invalid_mode", "allowed": ["overwrite", "append"]}
        if mode == "append":
            p.write_text(p.read_text(encoding="utf-8", errors="replace") + content, encoding="utf-8")
        else:
            p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(p), "bytes": p.stat().st_size}

    return ToolSpec(
        name="write_file",
        description="Write text content to a workspace file (overwrite or append).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path, relative to workspace root."},
                "content": {"type": "string", "description": "Full text content to write."},
                "mode": {"type": "string", "enum": ["overwrite", "append"], "default": "overwrite"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "workspace", "write"}),
        risk_level="high",
        read_only=False,
    )


__all__ = ["write_file_tool"]
