from __future__ import annotations

from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.path_guard import resolve_workspace_path


def bulk_apply_patch_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        patches = args.get("patches")
        if not isinstance(patches, list) or not patches:
            return {"ok": False, "error": "patches_required"}

        results: list[dict[str, Any]] = []

        for i, item in enumerate(patches):
            if not isinstance(item, dict):
                results.append({"index": i, "ok": False, "error": "invalid_item"})
                continue

            path_raw = str(item.get("path") or "").strip()
            content = item.get("content")
            expected_sha256 = item.get("expected_sha256")

            if not path_raw:
                results.append({"index": i, "ok": False, "error": "path_required"})
                continue
            if not isinstance(content, str):
                results.append({"index": i, "ok": False, "error": "content_required"})
                continue

            try:
                p = resolve_workspace_path(path_raw)
            except Exception as exc:
                results.append({"index": i, "ok": False, "error": "invalid_path", "detail": str(exc)})
                continue

            # Optional optimistic concurrency (match existing apply_patch semantics)
            if expected_sha256:
                import hashlib

                if p.exists() and p.is_file():
                    cur = p.read_bytes()
                    cur_sha = hashlib.sha256(cur).hexdigest()
                    if cur_sha != expected_sha256:
                        results.append(
                            {
                                "index": i,
                                "ok": False,
                                "error": "sha256_mismatch",
                                "path": str(p),
                                "expected_sha256": expected_sha256,
                                "actual_sha256": cur_sha,
                            }
                        )
                        continue

            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                results.append({"index": i, "ok": True, "path": str(p), "bytes": p.stat().st_size})
            except Exception as exc:
                results.append({"index": i, "ok": False, "error": "write_failed", "path": str(p), "detail": str(exc)})

        return {"ok": True, "results": results}

    return ToolSpec(
        name="bulk_apply_patch",
        description="Apply multiple file overwrites in one call (with optional sha256 preconditions).",
        parameters={
            "type": "object",
            "properties": {
                "patches": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                            "expected_sha256": {"type": "string"},
                        },
                        "required": ["path", "content"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["patches"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "workspace", "write"}),
        read_only=False,
        risk_level="high",
    )


__all__ = ["bulk_apply_patch_tool"]
