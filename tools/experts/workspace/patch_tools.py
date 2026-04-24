from __future__ import annotations

import hashlib
from typing import Any

from oclaw.tools.base import ToolSpec
from oclaw.tools.experts.workspace.workspace_base import resolve_workspace_path


def apply_patch_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        path = str(args.get("path") or "").strip()
        new_content = str(args.get("new_content") or "")
        expected_sha256 = str(args.get("expected_sha256") or "").strip()
        p = resolve_workspace_path(path)
        if p.exists() and p.is_file() and expected_sha256:
            cur = hashlib.sha256(p.read_bytes()).hexdigest()
            if cur != expected_sha256:
                return {
                    "ok": False,
                    "error": "sha_mismatch",
                    "path": str(p),
                    "expected_sha256": expected_sha256,
                    "current_sha256": cur,
                }
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(new_content, encoding="utf-8")
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        return {"ok": True, "path": str(p), "sha256": sha, "bytes": p.stat().st_size}

    return ToolSpec(
        name="apply_patch",
        description="Apply a full-file patch by overwriting a file with new content (optional sha256 precondition).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path, relative to workspace root."},
                "new_content": {"type": "string", "description": "New full file content."},
                "expected_sha256": {
                    "type": "string",
                    "description": "If provided, the current file sha256 must match (precondition).",
                },
            },
            "required": ["path", "new_content"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"workspace", "write"}),
    )


__all__ = ["apply_patch_tool"]

