"""Classify scheduled_job_run errors for Admin dashboards and ops triage."""

from __future__ import annotations

from typing import Any


def classify_scheduled_job_error(error: str | None, *, status: str | None = None) -> str:
    """Return a coarse failure_class for a scheduled job run.

    Classes: overlap | timeout | delivery | mcp | auth | cancelled | runtime | "" (success/empty).
    """
    st = str(status or "").strip().lower()
    err = str(error or "").strip()
    if st in {"success", "ok", "skipped"} and not err:
        return ""
    if st == "skipped" or "overlapping" in err.lower() or err.lower() == "overlapping_run":
        return "overlap"
    if not err and st not in {"failed", "error"}:
        return ""
    blob = err.lower()
    if "stale_running" in blob:
        return "stale"
    if any(x in blob for x in ("timeout", "timed out", "deadline", "read_timeout")):
        return "timeout"
    if any(
        x in blob
        for x in (
            "delivery",
            "enqueue_failed",
            "connection closed",
            "whatsapp",
            "weixin",
            "send_failed",
            "outbound",
        )
    ):
        return "delivery"
    if any(x in blob for x in ("insufficient_scope", "unauthorized", "forbidden", "permission denied", "auth")):
        return "auth"
    if any(x in blob for x in ("mcp", "unregistered tool", "tool_not_registered")):
        return "mcp"
    if any(x in blob for x in ("cancel", "interrupted", "stopped")):
        return "cancelled"
    if err:
        return "runtime"
    if st in {"failed", "error"}:
        return "runtime"
    return ""


def enrich_scheduled_job_run_dict(d: dict[str, Any]) -> dict[str, Any]:
    out = dict(d or {})
    fc = classify_scheduled_job_error(out.get("error"), status=str(out.get("status") or ""))
    if fc:
        out["failure_class"] = fc
    elif str(out.get("status") or "").strip().lower() in {"failed", "error"}:
        out["failure_class"] = "runtime"
    return out


__all__ = [
    "classify_scheduled_job_error",
    "enrich_scheduled_job_run_dict",
]
