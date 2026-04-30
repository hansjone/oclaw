from __future__ import annotations

from pathlib import Path
from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.path_guard import resolve_workspace_path


def multi_edit_file_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path") or "").strip()
        replacements = args.get("replacements") or []
        if not path:
            return {"ok": False, "error": "path_required"}
        if not isinstance(replacements, list) or not replacements:
            return {"ok": False, "error": "replacements_required"}

        try:
            p = resolve_workspace_path(path)
        except Exception as exc:
            return {"ok": False, "error": "invalid_path", "detail": str(exc)}

        if not p.exists() or not p.is_file():
            return {"ok": False, "error": "file_not_found", "path": str(p)}

        original = p.read_text(encoding="utf-8", errors="replace")
        text = original
        applied: list[dict[str, Any]] = []

        for item in replacements:
            if not isinstance(item, dict):
                return {"ok": False, "error": "invalid_replacement_item"}
            search = str(item.get("search") or "")
            replace = str(item.get("replace") or "")
            count = int(item.get("count") or 0)
            if not search:
                return {"ok": False, "error": "search_required"}
            occurrences = text.count(search)
            if occurrences == 0:
                applied.append({"search": search, "replaced": 0, "found": 0})
                continue
            if count and count > 0:
                text = text.replace(search, replace, count)
                applied.append({"search": search, "replaced": min(count, occurrences), "found": occurrences})
            else:
                text = text.replace(search, replace)
                applied.append({"search": search, "replaced": occurrences, "found": occurrences})

        if text != original:
            p.write_text(text, encoding="utf-8")

        return {
            "ok": True,
            "path": str(p),
            "changed": text != original,
            "bytes": p.stat().st_size,
            "applied": applied,
        }

    return ToolSpec(
        name="multi_edit_file",
        description="Apply multiple search/replace edits to a single workspace file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path."},
                "replacements": {
                    "type": "array",
                    "description": "List of replacement operations in order.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "search": {"type": "string", "description": "Text to find."},
                            "replace": {"type": "string", "description": "Replacement text."},
                            "count": {"type": "integer", "description": "Optional max occurrences to replace.", "default": 0},
                        },
                        "required": ["search", "replace"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["path", "replacements"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "workspace", "write"}),
        read_only=False,
        risk_level="high",
    )


__all__ = ["multi_edit_file_tool"]
