from __future__ import annotations

from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.path_guard import resolve_workspace_path


def glob_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        pattern = str(args.get("pattern") or "**/*").strip() or "**/*"
        max_results = int(args.get("max_results") or 200)
        root_arg = str(args.get("root") or "").strip()
        if not root_arg:
            base = resolve_workspace_path(".")
        else:
            base = resolve_workspace_path(root_arg)
            if not base.is_dir():
                return {"ok": False, "error": "not_a_directory", "path": str(base)}
        out: list[str] = []
        for p in base.glob(pattern):
            if p.is_dir():
                continue
            out.append(str(p.relative_to(base)))
            if len(out) >= max(1, min(max_results, 2000)):
                break
        return {
            "ok": True,
            "root": str(base),
            "pattern": pattern,
            "count": len(out),
            "files": out,
        }

    return ToolSpec(
        name="glob",
        description=(
            "List files under a directory matching a glob pattern. "
            "Default root is workspace root; set `root` to an absolute path (e.g. D:\\download) when needed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern relative to root, e.g. '**/*' or '*.pdf'.", "default": "**/*"},
                "root": {
                    "type": "string",
                    "description": "Optional directory to search under (absolute or workspace-relative). If omitted, uses workspace root.",
                },
                "max_results": {"type": "integer", "default": 200, "description": "Max number of files to return."},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "workspace"}),
        read_only=True,
        risk_level="low",
    )


__all__ = ["glob_tool"]
