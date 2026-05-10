from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.public.local_sdk import get_local_adapter


def search_files_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        pattern = str(args.get("pattern") or "").strip()
        root = str(args.get("root") or ".").strip() or "."
        file_glob = str(args.get("file_glob") or "**/*").strip() or "**/*"
        regex = bool(args.get("regex", True))
        max_matches = int(args.get("max_matches") or 200)
        return get_local_adapter().search_files(
            root=root,
            pattern=pattern,
            file_glob=file_glob,
            regex=regex,
            max_matches=max_matches,
        )

    return ToolSpec(
        name="search_files",
        description="Search file contents under a directory (regex or substring).",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex or substring pattern."},
                "root": {"type": "string", "default": ".", "description": "Root directory to search."},
                "file_glob": {"type": "string", "default": "**/*", "description": "File glob under root."},
                "regex": {"type": "boolean", "default": True, "description": "Treat pattern as regex if true."},
                "max_matches": {"type": "integer", "default": 200, "description": "Max matches to return."},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "local", "workspace", "read"}),
        risk_level="low",
        read_only=True,
        timeout_s=20.0,
    )


__all__ = ["search_files_tool"]
