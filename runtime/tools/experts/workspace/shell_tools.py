from __future__ import annotations

import subprocess
from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.experts.workspace.workspace_base import resolve_workspace_path, truncate_text


def run_command_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        import os

        if str(os.getenv("AIA_ENABLE_RUN_COMMAND") or "").strip().lower() not in ("1", "true", "yes", "on"):
            return {
                "ok": False,
                "error": "disabled",
                "hint": "Set AIA_ENABLE_RUN_COMMAND=1 to enable this high-risk tool.",
            }
        command = str(args.get("command") or "").strip()
        cwd = str(args.get("cwd") or "").strip()
        timeout_s = float(args.get("timeout_s") or 30.0)
        max_output_chars = int(args.get("max_output_chars") or 20000)
        if not command:
            return {"ok": False, "error": "command_required"}
        workdir = resolve_workspace_path(cwd or ".")
        try:
            run_kwargs: dict[str, Any] = {
                "cwd": str(workdir),
                "shell": True,
                "capture_output": True,
                "text": True,
                "timeout": max(1.0, min(timeout_s, 600.0)),
            }
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                run_kwargs["startupinfo"] = startupinfo
                run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            cp = subprocess.run(
                command,
                **run_kwargs,
            )
            out = (cp.stdout or "") + (("\n" + cp.stderr) if cp.stderr else "")
            out = truncate_text(out, limit=max(1000, min(max_output_chars, 200000)))
            return {
                "ok": True,
                "command": command,
                "cwd": str(workdir),
                "exit_code": int(cp.returncode),
                "output": out,
            }
        except subprocess.TimeoutExpired as e:
            partial = ""
            try:
                partial = ((e.stdout or "") + ("\n" + (e.stderr or "") if e.stderr else "")).strip()
            except Exception:
                partial = ""
            return {
                "ok": False,
                "error": "timeout",
                "command": command,
                "cwd": str(workdir),
                "timeout_s": timeout_s,
                "output": truncate_text(partial, limit=max_output_chars),
            }
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}", "command": command, "cwd": str(workdir)}

    return ToolSpec(
        name="run_command",
        description="Run a shell command inside the workspace (captured output, timeout).",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run."},
                "cwd": {"type": "string", "description": "Working directory relative to workspace.", "default": "."},
                "timeout_s": {"type": "number", "default": 30.0, "description": "Command timeout in seconds."},
                "max_output_chars": {"type": "integer", "default": 20000, "description": "Max characters to return."},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"workspace", "exec"}),
    )


__all__ = ["run_command_tool"]

