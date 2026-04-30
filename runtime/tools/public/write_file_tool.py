from __future__ import annotations

from pathlib import Path
from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.path_guard import resolve_workspace_path


def write_file_tool() -> ToolSpec:
    def _sandbox_base_dir() -> Path:
        return Path("data") / "workspace"

    def _normalize_write_path(path: str) -> str:
        raw = str(path or "").strip().strip('"').strip("'")
        if not raw:
            raise ValueError("path_required")
        p = Path(raw)
        base = _sandbox_base_dir()
        if p.is_absolute():
            name = str(p.name or "").strip()
            if not name:
                raise ValueError("path_required")
            return str(base / name)
        rel = raw.lstrip("./\\")
        if not rel:
            raise ValueError("path_required")
        return str(base / rel)

    def _handler(args: dict[str, Any]) -> dict[str, Any]:
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
        handler=_handler,
        tags=frozenset({"public", "workspace", "write"}),
        risk_level="high",
        read_only=False,
    )


__all__ = ["write_file_tool"]
