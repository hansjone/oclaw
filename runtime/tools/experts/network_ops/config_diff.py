from __future__ import annotations

import difflib
from typing import Any

from oclaw.runtime.tools.base import ToolSpec


def config_diff_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        left_name = str(args.get("left_name") or "left")
        right_name = str(args.get("right_name") or "right")
        left = str(args.get("left") or "")
        right = str(args.get("right") or "")
        left_lines = left.splitlines(keepends=False)
        right_lines = right.splitlines(keepends=False)
        diff_lines = list(
            difflib.unified_diff(left_lines, right_lines, fromfile=left_name, tofile=right_name, lineterm="")
        )
        return {"ok": True, "diff": "\n".join(diff_lines), "changed": left_lines != right_lines}

    return ToolSpec(
        name="config_diff",
        description="Compare two configuration texts and return a unified diff.",
        parameters={
            "type": "object",
            "properties": {
                "left_name": {"type": "string", "description": "Optional label for the left side."},
                "right_name": {"type": "string", "description": "Optional label for the right side."},
                "left": {"type": "string", "description": "Left configuration text."},
                "right": {"type": "string", "description": "Right configuration text."},
            },
            "required": ["left", "right"],
            "additionalProperties": False,
        },
        handler=handler,
    )


__all__ = ["config_diff_tool"]
