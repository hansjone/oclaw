from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.local_sdk import get_local_adapter


def local_edit_file_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path") or "").strip()
        if not path:
            return {"ok": False, "error_code": "path_required", "error": "path_required"}

        search = args.get("search")
        replace = args.get("replace")
        start_line = args.get("start_line")
        end_line = args.get("end_line")
        replacement = args.get("replacement")

        has_search = search is not None
        has_range = start_line is not None or end_line is not None or replacement is not None
        if has_search and has_range:
            return {
                "ok": False,
                "error_code": "invalid_edit_arguments",
                "error": "choose search/replace or line-range replacement, not both",
            }
        if not has_search and not has_range:
            return {
                "ok": False,
                "error_code": "invalid_edit_arguments",
                "error": "missing edit arguments",
            }

        return get_local_adapter().edit_file(
            path=path,
            search=str(search) if has_search else None,
            replace=str(replace) if replace is not None else None,
            start_line=int(start_line) if start_line is not None else None,
            end_line=int(end_line) if end_line is not None else None,
            replacement=str(replacement) if replacement is not None else None,
        )

    return ToolSpec(
        name="local_edit_file",
        description="Edit partial file content via local backend.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path."},
                "search": {"type": "string", "description": "Search text for single replace mode."},
                "replace": {"type": "string", "description": "Replacement text for search mode."},
                "start_line": {"type": "integer", "description": "Start line for line-range replace mode."},
                "end_line": {"type": "integer", "description": "End line for line-range replace mode."},
                "replacement": {"type": "string", "description": "Replacement content for line-range mode."},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "workspace", "write", "edit"}),
        risk_level="high",
        timeout_s=30.0,
        read_only=False,
    )


__all__ = ["local_edit_file_tool"]
