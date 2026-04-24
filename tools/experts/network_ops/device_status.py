from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

from oclaw.tools.base import ToolSpec

_TTL_RE = re.compile(r"\bttl[= ]\d+\b", re.IGNORECASE)
_AVG_WIN_RE = re.compile(r"Average\s*=\s*(\d+)\s*ms", re.IGNORECASE)
_AVG_NIX_RE = re.compile(r"=\s*[\d.]+/([\d.]+)/[\d.]+/[\d.]+\s*ms")


def _ping(host: str, count: int, timeout_ms: int) -> dict[str, Any]:
    try:
        if sys.platform == "win32":
            cmd = ["ping", "-n", str(count), "-w", str(timeout_ms), host]
            timeout_s = max(1, (timeout_ms * count) / 1000 + 2)
        else:
            timeout_s_each = max(1, int(round(timeout_ms / 1000)))
            cmd = ["ping", "-c", str(count), "-W", str(timeout_s_each), host]
            timeout_s = max(1, timeout_s_each * count + 2)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError:
        return {"ok": False, "error": "ping command not found on this system"}
    except subprocess.TimeoutExpired:
        return {"ok": True, "reachable": False, "output": "ping timed out"}

    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    reachable = proc.returncode == 0 and bool(_TTL_RE.search(output))
    avg_ms = None
    if sys.platform == "win32":
        m = _AVG_WIN_RE.search(output)
        if m:
            try:
                avg_ms = int(m.group(1))
            except ValueError:
                avg_ms = None
    else:
        m2 = _AVG_NIX_RE.search(output)
        if m2:
            try:
                avg_ms = int(float(m2.group(1)))
            except ValueError:
                avg_ms = None
    return {"ok": True, "reachable": reachable, "avg_ms": avg_ms, "returncode": proc.returncode, "output": output}


def device_status_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        host = str(args.get("host"))
        count = int(args.get("count") or 2)
        timeout_ms = int(args.get("timeout_ms") or 1000)
        if count < 1 or count > 10:
            return {"ok": False, "error": "count must be between 1 and 10"}
        if timeout_ms < 200 or timeout_ms > 10000:
            return {"ok": False, "error": "timeout_ms must be between 200 and 10000"}
        return _ping(host=host, count=count, timeout_ms=timeout_ms)

    return ToolSpec(
        name="device_status",
        description="Check host reachability using ICMP ping (system ping binary).",
        parameters={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Hostname or IP address."},
                "count": {"type": "integer", "description": "Number of ping probes. Default 2."},
                "timeout_ms": {"type": "integer", "description": "Per-packet timeout in milliseconds. Default 1000."},
            },
            "required": ["host"],
            "additionalProperties": False,
        },
        handler=handler,
    )


__all__ = ["device_status_tool"]
