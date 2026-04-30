from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.path_guard import resolve_workspace_path, truncate_text


def search_files_context_tool() -> ToolSpec:
    def _iter_files(root: Path, file_glob: str) -> list[Path]:
        if root.is_file():
            return [root]
        try:
            return [p for p in root.rglob(file_glob) if p.is_file()]
        except Exception:
            return []

    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        root_raw = str(args.get("root") or ".").strip()
        file_glob = str(args.get("file_glob") or "**/*").strip() or "**/*"
        pattern = str(args.get("pattern") or "").strip()
        regex = bool(args.get("regex", True))
        max_matches = int(args.get("max_matches") or 200)
        context_lines = int(args.get("context_lines") or 2)
        if max_matches <= 0:
            max_matches = 1
        if context_lines < 0:
            context_lines = 0

        try:
            root = resolve_workspace_path(root_raw)
        except Exception as exc:
            return {"ok": False, "error": "invalid_root", "detail": str(exc)}

        if not pattern:
            return {"ok": False, "error": "pattern_required"}

        matcher = re.compile(pattern) if regex else None
        out: list[dict[str, Any]] = []
        scanned = 0

        for fp in _iter_files(root, file_glob):
            scanned += 1
            if len(out) >= max_matches:
                break
            try:
                lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue

            for idx, line in enumerate(lines):
                hit = matcher.search(line) if matcher else (pattern in line)
                if not hit:
                    continue
                start = max(0, idx - context_lines)
                end = min(len(lines), idx + context_lines + 1)
                out.append(
                    {
                        "path": str(fp),
                        "line": idx + 1,
                        "match": line,
                        "context": [f"{i + 1}|{lines[i]}" for i in range(start, end)],
                    }
                )
                if len(out) >= max_matches:
                    break

        return {
            "ok": True,
            "root": str(root),
            "file_glob": file_glob,
            "pattern": pattern,
            "regex": regex,
            "scanned_files": scanned,
            "matches": out,
        }

    return ToolSpec(
        name="search_files_context",
        description="Search files under a root and return matched lines with surrounding context.",
        parameters={
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Directory to search under."},
                "file_glob": {"type": "string", "description": "File glob under root.", "default": "**/*"},
                "pattern": {"type": "string", "description": "Regex or substring pattern."},
                "regex": {"type": "boolean", "description": "Treat pattern as regex if true.", "default": True},
                "max_matches": {"type": "integer", "description": "Max matches to return.", "default": 200},
                "context_lines": {"type": "integer", "description": "Number of lines of context on each side.", "default": 2},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "search", "workspace"}),
        read_only=True,
        risk_level="low",
    )


__all__ = ["search_files_context_tool"]
