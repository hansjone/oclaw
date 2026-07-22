from __future__ import annotations

from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.path_guard import resolve_workspace_path
from svc.jobs.background_jobs import (
    DEFAULT_TIMEOUT_S,
    MAX_TIMEOUT_S,
    get_job_store,
    is_shell_exec_enabled,
)


def start_job_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        enabled, hint = is_shell_exec_enabled()
        if not enabled:
            return {"ok": False, "error": "disabled", "hint": hint}
        command = str(args.get("command") or "").strip()
        if not command:
            return {"ok": False, "error": "command_required"}
        cwd_raw = str(args.get("cwd") or "").strip() or "."
        try:
            cwd = str(resolve_workspace_path(cwd_raw))
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        timeout_s = args.get("timeout_s")
        name = str(args.get("name") or "").strip()
        notify = args.get("notify") if isinstance(args.get("notify"), dict) else None
        return get_job_store().start(
            command=command,
            cwd=cwd,
            timeout_s=int(timeout_s) if timeout_s is not None else DEFAULT_TIMEOUT_S,
            name=name,
            notify=notify,
        )

    return ToolSpec(
        name="start_job",
        description=(
            "Start a long-running shell command in the background and return job_id immediately "
            f"(default timeout {DEFAULT_TIMEOUT_S}s / 2h, max {MAX_TIMEOUT_S}s / 3h). "
            "The process keeps running after this agent turn ends or the chat disconnects. "
            "Tell the user the job_id and end the turn — do NOT sleep for hours. "
            "Resume later with get_job/list_jobs. Optional notify={channel,chat_id,...} pings the "
            "channel when the job finishes. Same enable gate as run_command (AIA_ENABLE_RUN_COMMAND)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run in background."},
                "cwd": {"type": "string", "description": "Working directory (workspace-relative or allowed path)."},
                "timeout_s": {
                    "type": "integer",
                    "description": f"Kill after N seconds (default {DEFAULT_TIMEOUT_S}, max {MAX_TIMEOUT_S}).",
                    "default": DEFAULT_TIMEOUT_S,
                },
                "name": {"type": "string", "description": "Optional human label for the job."},
                "notify": {
                    "type": "object",
                    "description": (
                        "Optional channel ping on completion. "
                        "Fields: channel (whatsapp/weixin), chat_id, account_id?, tenant_id?, "
                        "context_token? (weixin), message? (custom text)."
                    ),
                    "properties": {
                        "channel": {"type": "string"},
                        "chat_id": {"type": "string"},
                        "account_id": {"type": "string"},
                        "tenant_id": {"type": "string"},
                        "context_token": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "exec", "job"}),
        risk_level="high",
        read_only=False,
        timeout_s=30.0,
    )


def get_job_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        job_id = str(args.get("job_id") or "").strip()
        log_tail = int(args.get("log_tail_chars") or 4000)
        return get_job_store().get(job_id, log_tail_chars=log_tail)

    return ToolSpec(
        name="get_job",
        description=(
            "Get background job status by job_id (running/succeeded/failed/timeout/cancelled), "
            "exit_code, and stdout/stderr tails. Poll until done=true."
        ),
        parameters={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job id returned by start_job."},
                "log_tail_chars": {
                    "type": "integer",
                    "description": "Max characters of each log tail (default 4000).",
                    "default": 4000,
                },
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "job", "read"}),
        risk_level="low",
        read_only=True,
        timeout_s=10.0,
    )


def cancel_job_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        enabled, hint = is_shell_exec_enabled()
        if not enabled:
            return {"ok": False, "error": "disabled", "hint": hint}
        job_id = str(args.get("job_id") or "").strip()
        return get_job_store().cancel(job_id)

    return ToolSpec(
        name="cancel_job",
        description="Cancel a running background job (best-effort process tree kill).",
        parameters={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job id returned by start_job."},
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "exec", "job"}),
        risk_level="high",
        read_only=False,
        timeout_s=20.0,
    )


def list_jobs_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        limit = int(args.get("limit") or 20)
        return get_job_store().list_jobs(limit=limit)

    return ToolSpec(
        name="list_jobs",
        description="List recent background jobs (id, name, status, timestamps).",
        parameters={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max jobs to return (default 20).", "default": 20},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "job", "read"}),
        risk_level="low",
        read_only=True,
        timeout_s=10.0,
    )


__all__ = ["start_job_tool", "get_job_tool", "cancel_job_tool", "list_jobs_tool"]
