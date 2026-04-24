from __future__ import annotations

import re
from collections import Counter
from typing import Any

from oclaw.runtime.tools.base import ToolSpec

_LEVEL_RE = re.compile(r"\b(ERROR|WARN|WARNING|INFO|DEBUG)\b", re.IGNORECASE)


def log_analysis_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("log") or "")
        max_lines = int(args.get("max_lines") or 2000)
        lines = text.splitlines()
        if len(lines) > max_lines:
            lines = lines[-max_lines:]

        levels: Counter[str] = Counter()
        samples: dict[str, list[str]] = {"ERROR": [], "WARN": []}
        for line in lines:
            m = _LEVEL_RE.search(line)
            if not m:
                continue
            level = m.group(1).upper()
            if level == "WARNING":
                level = "WARN"
            if level in ("ERROR", "WARN", "INFO", "DEBUG"):
                levels[level] += 1
                if level in samples and len(samples[level]) < 5:
                    samples[level].append(line[:500])

        top_lines = [l[:500] for l in lines[-20:]]
        return {"ok": True, "line_count": len(lines), "level_count": dict(levels), "samples": samples, "tail": top_lines}

    return ToolSpec(
        name="log_analysis",
        description="Summarize log text: counts of ERROR/WARN/INFO/DEBUG lines, sample lines, and the last lines (tail).",
        parameters={
            "type": "object",
            "properties": {
                "log": {"type": "string", "description": "Log text to analyze."},
                "max_lines": {"type": "integer", "description": "Maximum number of lines to analyze (uses the tail if exceeded). Default 2000."},
            },
            "required": ["log"],
            "additionalProperties": False,
        },
        handler=handler,
    )


__all__ = ["log_analysis_tool"]
