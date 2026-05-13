from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.path_guard import resolve_workspace_path


def list_workspace_tree_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        root_raw = str(args.get("root") or ".").strip()
        max_depth = int(args.get("max_depth") or 4)
        max_entries = int(args.get("max_entries") or 300)
        show_files = bool(args.get("show_files", True))
        if max_depth < 0:
            max_depth = 0
        if max_entries <= 0:
            max_entries = 1

        try:
            root = resolve_workspace_path(root_raw)
        except Exception as exc:
            return {"ok": False, "error": "invalid_root", "detail": str(exc)}

        entries: list[dict[str, Any]] = []

        def walk(p: Path, depth: int) -> None:
            if len(entries) >= max_entries or depth > max_depth:
                return
            try:
                children = sorted(list(p.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
            except Exception:
                return
            for child in children:
                if len(entries) >= max_entries:
                    return
                is_dir = child.is_dir()
                if is_dir or show_files:
                    entries.append(
                        {
                            "path": str(child),
                            "name": child.name,
                            "type": "dir" if is_dir else "file",
                            "depth": depth,
                            "size": child.stat().st_size if child.exists() and child.is_file() else None,
                        }
                    )
                if is_dir:
                    walk(child, depth + 1)

        if root.exists():
            walk(root, 0)

        return {
            "ok": True,
            "root": str(root),
            "max_depth": max_depth,
            "max_entries": max_entries,
            "entries": entries,
        }

    return ToolSpec(
        name="list_workspace_tree",
        description="List a workspace tree with depth-limited entries.",
        parameters={
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Directory to start from.", "default": "."},
                "max_depth": {"type": "integer", "description": "Maximum recursion depth.", "default": 4},
                "max_entries": {"type": "integer", "description": "Maximum entries to return.", "default": 300},
                "show_files": {"type": "boolean", "description": "Whether to include files as well as directories.", "default": True},
            },
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "workspace"}),
        read_only=True,
        risk_level="low",
    )


__all__ = ["list_workspace_tree_tool"]
