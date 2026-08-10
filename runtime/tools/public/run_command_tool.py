from __future__ import annotations

from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.public.local_sdk import get_local_adapter

_XLSX_SHELL_MARKERS = (
    "openpyxl",
    "xlsxwriter",
    "to_excel(",
    "workbook(",
    "load_workbook(",
)


def _looks_like_xlsx_via_shell(command: str) -> bool:
    """Detect agents trying to build Excel via shell/python instead of write_xlsx."""
    low = str(command or "").lower()
    if not low:
        return False
    if any(m in low for m in _XLSX_SHELL_MARKERS):
        return True
    if ".xlsx" in low and any(tok in low for tok in ("python", "pip", "pandas", "-c ", "import ")):
        return True
    return False


def run_command_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        command = str(
            args.get("command") or args.get("cmd") or args.get("shell") or args.get("script") or ""
        ).strip()
        if not command:
            return {
                "ok": False,
                "error_code": "command_required",
                "error": "command_required",
                "hint": "Pass command (aliases: cmd, shell).",
                "example": {"command": "echo hello", "timeout": 60},
            }
        if _looks_like_xlsx_via_shell(command):
            return {
                "ok": False,
                "error_code": "xlsx_via_shell_forbidden",
                "error": "xlsx_via_shell_forbidden",
                "failure_class": "schema_validation",
                "retry_forbidden": True,
                "hint": (
                    "Do not build Excel via run_command/openpyxl/pandas. "
                    "Use ume_alarm_xlsx_report or write_xlsx(deliverable=true) instead."
                ),
                "fallback_tools": ["ume_alarm_xlsx_report", "write_xlsx"],
            }
        cwd = str(args.get("cwd") or args.get("workdir") or "").strip() or None
        timeout = int(args.get("timeout") or 300)
        return get_local_adapter().run_command(command=command, cwd=cwd, timeout=timeout)

    return ToolSpec(
        name="run_command",
        description=(
            "Run a shell command via local backend. Prefer cmd aliases: command/cmd/shell. "
            "Do not use this to build .xlsx (use write_xlsx / ume_alarm_xlsx_report)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute."},
                "cmd": {"type": "string", "description": "Alias for command."},
                "shell": {"type": "string", "description": "Alias for command."},
                "script": {"type": "string", "description": "Alias for command."},
                "cwd": {"type": "string", "description": "Optional working directory."},
                "workdir": {"type": "string", "description": "Alias for cwd."},
                "timeout": {"type": "integer", "description": "Timeout in seconds.", "default": 300},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "exec"}),
        risk_level="high",
        timeout_s=620.0,
        read_only=False,
    )


__all__ = ["run_command_tool", "_looks_like_xlsx_via_shell"]
