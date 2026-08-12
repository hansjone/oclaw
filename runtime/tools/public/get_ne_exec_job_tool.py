from __future__ import annotations

from typing import Any

from runtime.tools.base import ToolSpec
from svc.jobs.ne_exec_jobs import get_ne_exec_job


def get_ne_exec_job_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        return get_ne_exec_job(str(args.get("job_id") or "").strip())

    return ToolSpec(
        name="get_ne_exec_job",
        description=(
            "Poll a background execManagedNe job started with async=true (or auto-async for large batches). "
            "Pass job_id from the async ack. When status is succeeded/failed/timeout, result contains the full CLI output."
        ),
        parameters={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job id returned by async execManagedNe."},
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "jobs", "read"}),
        read_only=True,
        risk_level="low",
        timeout_s=8.0,
    )


__all__ = ["get_ne_exec_job_tool"]
