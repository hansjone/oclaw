from __future__ import annotations

import subprocess
import re
from pathlib import Path
from typing import Any

from oclaw.platform.config.paths import db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.experts.workspace.workspace_base import (
    resolve_workspace_path,
    truncate_text,
    workspace_root,
)


def run_command_tool() -> ToolSpec:
    _LEADING_CD_CHAIN_RE = re.compile(
        r"^\s*(?:(?:[A-Za-z]:)\s*&&\s*)?(?:@echo\s+off\s*&&\s*)?cd\s+(?:/d\s+)?(?:\"[^\"]+\"|[^&]+?)\s*&&\s*(.+)$",
        re.IGNORECASE | re.DOTALL,
    )

    def _run_command_enabled() -> bool:
        import os

        try:
            raw_setting = str(SqliteStore(db_path()).get_setting("AIA_ENABLE_RUN_COMMAND") or "").strip().lower()
            if raw_setting in ("0", "false", "no", "off"):
                return False
            if raw_setting in ("1", "true", "yes", "on"):
                return True
        except Exception:
            pass

        raw_env = str(os.getenv("AIA_ENABLE_RUN_COMMAND") or "").strip().lower()
        if raw_env in ("0", "false", "no", "off"):
            return False
        if raw_env in ("1", "true", "yes", "on"):
            return True
        # Default disabled when unset (explicit opt-in only).
        return False

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        import os

        def _default_exec_dir() -> str:
            return str(resolve_workspace_path("data/workspace"))

        def _strip_leading_cd_chain(cmd: str) -> tuple[str, bool]:
            raw = str(cmd or "")
            changed = False
            out = raw
            # Strip repeated leading "cd ... &&" so default sandbox cwd cannot be bypassed by habit.
            for _ in range(3):
                m = _LEADING_CD_CHAIN_RE.match(out)
                if not m:
                    break
                tail = str(m.group(1) or "").strip()
                if not tail:
                    break
                out = tail
                changed = True
            return out, changed

        def _rewrite_workspace_absolute_refs(cmd: str, *, workdir: str) -> tuple[str, bool]:
            raw = str(cmd or "")
            root = str(workspace_root())
            if not raw or not root:
                return raw, False
            root_norm = root.rstrip("\\/")
            changed = False
            out = raw
            marker = root_norm + "\\"
            if marker.lower() not in out.lower():
                return out, False
            idx = 0
            rebuilt = []
            low = out.lower()
            marker_low = marker.lower()
            while True:
                pos = low.find(marker_low, idx)
                if pos < 0:
                    rebuilt.append(out[idx:])
                    break
                rebuilt.append(out[idx:pos])
                tail_start = pos + len(marker)
                tail_end = tail_start
                while tail_end < len(out) and out[tail_end] not in ('"', "'", " ", "\t", "\r", "\n"):
                    tail_end += 1
                rel_tail = out[tail_start:tail_end]
                candidate = str(Path(workdir) / rel_tail)
                if Path(candidate).exists():
                    rebuilt.append(candidate)
                    changed = True
                else:
                    rebuilt.append(out[pos:tail_end])
                idx = tail_end
            return "".join(rebuilt), changed

        def _rewrite_python_script_arg(cmd: str, *, workdir: str) -> tuple[str, bool]:
            raw = str(cmd or "").strip()
            if not raw:
                return raw, False
            m = re.match(r'^\s*(python|py)\s+("([^"]+\.py)"|([^\s]+\.py))(\s+.*)?$', raw, flags=re.IGNORECASE)
            if not m:
                return raw, False
            script = str(m.group(3) or m.group(4) or "").strip()
            if not script:
                return raw, False
            # Absolute path is handled by workspace-absolute rewrite already.
            sp = Path(script)
            if sp.is_absolute():
                return raw, False
            base = str(Path(script).name or "").strip()
            if not base:
                return raw, False
            # Deterministic policy: always bind python script arg to sandbox root.
            rel = base
            quote = '"' if " " in rel else ""
            prefix = str(m.group(1) or "python")
            rest = str(m.group(5) or "")
            return f"{prefix} {quote}{rel}{quote}{rest}", True

        if not _run_command_enabled():
            return {
                "ok": False,
                "error": "disabled",
                "hint": "Enable run_command in Admin -> Plugins -> Tool Policy.",
            }
        command = str(args.get("command") or "").strip()
        cwd = str(args.get("cwd") or "").strip()
        timeout_s = float(args.get("timeout_s") or 30.0)
        max_output_chars = int(args.get("max_output_chars") or 20000)
        if not command:
            return {"ok": False, "error": "command_required"}
        normalized_cd_removed = False
        command_rewritten = False
        cwd_redirected_to_sandbox = False
        script_path_rewritten = False
        original_command = command
        # Hard policy: always execute in sandbox root, ignore caller-supplied cwd.
        workdir = _default_exec_dir()
        cwd_redirected_to_sandbox = bool(str(cwd or "").strip() and str(cwd).strip() not in {".", "./", ".\\"})
        command, normalized_cd_removed = _strip_leading_cd_chain(command)
        command, command_rewritten = _rewrite_workspace_absolute_refs(command, workdir=workdir)
        command, script_path_rewritten = _rewrite_python_script_arg(command, workdir=workdir)
        try:
            os.makedirs(workdir, exist_ok=True)
        except Exception:
            pass
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
            stdout_text = str(cp.stdout or "")
            stderr_text = str(cp.stderr or "")
            out_raw = stdout_text + (("\n" + stderr_text) if stderr_text else "")
            out_limit = max(1000, min(max_output_chars, 200000))
            out = truncate_text(out_raw, limit=out_limit)
            out_truncated = len(out_raw) > out_limit
            out_empty = (len(str(out_raw or "").strip()) == 0)
            exit_code = int(cp.returncode)
            ok_flag = exit_code == 0
            return {
                "ok": bool(ok_flag),
                "command": command,
                "cwd": str(workdir),
                "exit_code": exit_code,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "output": out,
                "output_chars": int(len(out_raw)),
                "output_empty": bool(out_empty),
                "output_truncated": bool(out_truncated),
                "output_not_truncated": bool(not out_truncated),
                "normalized_cd_removed": bool(normalized_cd_removed),
                "cwd_redirected_to_sandbox": bool(cwd_redirected_to_sandbox),
                "command_rewritten": bool(command_rewritten),
                "script_path_rewritten": bool(script_path_rewritten),
                "original_command": original_command,
                "error_code": ("" if ok_flag else "command_exit_nonzero"),
                "output_hint": (
                    "Command produced empty stdout/stderr; this is not system truncation. "
                    "Do not claim truncation unless output_truncated=true."
                    if out_empty
                    else ""
                ),
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
                "output_empty": len(str(partial or "").strip()) == 0,
                "output_truncated": len(str(partial or "")) > int(max_output_chars or 0),
                "normalized_cd_removed": bool(normalized_cd_removed),
                "cwd_redirected_to_sandbox": bool(cwd_redirected_to_sandbox),
                "command_rewritten": bool(command_rewritten),
                "script_path_rewritten": bool(script_path_rewritten),
                "original_command": original_command,
            }
        except Exception as e:
            return {
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
                "command": command,
                "cwd": str(workdir),
                "normalized_cd_removed": bool(normalized_cd_removed),
                "cwd_redirected_to_sandbox": bool(cwd_redirected_to_sandbox),
                "command_rewritten": bool(command_rewritten),
                "script_path_rewritten": bool(script_path_rewritten),
                "original_command": original_command,
            }

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

