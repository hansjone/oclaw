from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.experts.workspace.workspace_base import (
    resolve_workspace_path,
)


def read_file_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
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
        # 1-indexed offsets; negative counts from end
        if offset < 0:
            start = max(0, len(text) + offset)
        else:
            start = max(0, offset - 1)
        end = min(len(text), start + min(limit, 2000))
        out_lines = [f"{i+1}|{text[i]}" for i in range(start, end)]
        blob = p.read_bytes()
        sha = hashlib.sha256(blob).hexdigest()
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
        handler=handler,
        tags=frozenset({"workspace"}),
        read_only=True,
    )


def write_file_tool() -> ToolSpec:
    def _sandbox_base_dir() -> Path:
        return Path("data") / "workspace"

    def _normalize_write_path(path: str) -> str:
        raw = str(path or "").strip().strip('"').strip("'")
        if not raw:
            raise ValueError("path_required")
        p = Path(raw)
        base = _sandbox_base_dir()
        # Enforce sandbox for absolute paths as well.
        if p.is_absolute():
            # Collapse absolute user path into sandbox-relative target to prevent
            # writes to repo root or arbitrary host locations.
            name = str(p.name or "").strip()
            if not name:
                raise ValueError("path_required")
            return str(base / name)
        # Keep generated files out of repo root: default relative writes go under data/workspace/...
        rel = raw.lstrip("./\\")
        if not rel:
            raise ValueError("path_required")
        return str(base / rel)

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path") or "").strip()
        content = str(args.get("content") or "")
        mode = str(args.get("mode") or "overwrite").strip().lower()
        try:
            normalized = _normalize_write_path(path)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        p = resolve_workspace_path(normalized)
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
        handler=handler,
        tags=frozenset({"workspace", "write"}),
    )


def list_files_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
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
            rel = str(p.relative_to(base))
            out.append(rel)
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
            "Default root is the workspace root; set `root` to an absolute path (e.g. D:\\\\download) when the user names a folder outside the repo — "
            "this respects gateway workspace path policy. Prefer this over MCP filesystem list_directory when the user path may be outside MCP's configured roots."
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
        handler=handler,
        tags=frozenset({"workspace"}),
        read_only=True,
    )


__all__ = ["read_file_tool", "write_file_tool", "list_files_tool"]

