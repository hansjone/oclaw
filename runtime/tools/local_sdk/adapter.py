from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Any

from oclaw.runtime.tools.experts.workspace.workspace_base import resolve_workspace_path, truncate_text


@dataclass(frozen=True)
class LocalAdapterError(Exception):
    error_code: str
    message: str

    def as_result(self) -> dict[str, Any]:
        return {"ok": False, "error_code": self.error_code, "error": self.message}


class LocalAdapter:
    """Self-implemented local backend (cross-platform)."""

    def __init__(self) -> None:
        self._init_error: LocalAdapterError | None = None

    def run_command(self, *, command: str, cwd: str | None = None, timeout: int = 30) -> dict[str, Any]:
        cmd = str(command or "").strip()
        if not cmd:
            return {"ok": False, "error_code": "command_required", "error": "command_required"}
        try:
            timeout_s = max(1, min(int(timeout or 30), 600))
            workdir = str(resolve_workspace_path(cwd or "."))
            run_kwargs: dict[str, Any] = {
                "cwd": workdir,
                "shell": True,
                "capture_output": True,
                "text": True,
                "timeout": float(timeout_s),
            }
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                run_kwargs["startupinfo"] = startupinfo
                run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            cp = subprocess.run(cmd, **run_kwargs)
            stdout = str(cp.stdout or "")
            stderr = str(cp.stderr or "")
            combined = stdout + (("\n" + stderr) if stderr else "")
            return {
                "ok": int(cp.returncode) == 0,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": int(cp.returncode),
                "output": truncate_text(combined, limit=20000),
                "cwd": workdir,
            }
        except subprocess.TimeoutExpired as exc:
            partial = (str(exc.stdout or "") + ("\n" + str(exc.stderr or "") if exc.stderr else "")).strip()
            return {
                "ok": False,
                "error_code": "command_timeout",
                "error": "command_timeout",
                "stdout": str(exc.stdout or ""),
                "stderr": str(exc.stderr or ""),
                "output": truncate_text(partial, limit=20000),
            }
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}"}

    def read_file(
        self,
        *,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> dict[str, Any]:
        target = str(path or "").strip()
        if not target:
            return {"ok": False, "error_code": "path_required", "error": "path_required"}
        try:
            p = resolve_workspace_path(target)
            if not p.exists() or not p.is_file():
                return {"ok": False, "error_code": "file_not_found", "error": "file_not_found", "path": str(p)}
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            s = max(1, int(start_line or 1))
            e = int(end_line or len(lines))
            e = max(s, min(e, len(lines)))
            content = "\n".join(lines[s - 1 : e])
            return {
                "ok": True,
                "path": str(p),
                "start_line": s,
                "end_line": e,
                "total_lines": len(lines),
                "content": content,
            }
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}"}

    def write_file(self, *, path: str, content: str, mode: str = "overwrite") -> dict[str, Any]:
        target = str(path or "").strip()
        if not target:
            return {"ok": False, "error_code": "path_required", "error": "path_required"}
        write_mode = str(mode or "overwrite").strip().lower()
        if write_mode not in {"overwrite", "append"}:
            return {"ok": False, "error_code": "invalid_mode", "error": "invalid_mode"}
        try:
            p = resolve_workspace_path(target)
            p.parent.mkdir(parents=True, exist_ok=True)
            if write_mode == "append" and p.exists():
                merged = p.read_text(encoding="utf-8", errors="replace") + str(content or "")
                p.write_text(merged, encoding="utf-8")
            else:
                p.write_text(str(content or ""), encoding="utf-8")
            return {"ok": True, "path": str(p), "bytes": int(p.stat().st_size), "mode": write_mode}
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}"}

    def edit_file(
        self,
        *,
        path: str,
        search: str | None = None,
        replace: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        replacement: str | None = None,
    ) -> dict[str, Any]:
        target = str(path or "").strip()
        if not target:
            return {"ok": False, "error_code": "path_required", "error": "path_required"}
        try:
            p = resolve_workspace_path(target)
            if not p.exists() or not p.is_file():
                return {"ok": False, "error_code": "file_not_found", "error": "file_not_found", "path": str(p)}
            text = p.read_text(encoding="utf-8", errors="replace")
            if search is not None:
                needle = str(search)
                if needle not in text:
                    return {"ok": False, "error_code": "search_not_found", "error": "search_not_found"}
                new_text = text.replace(needle, str(replace or ""), 1)
                p.write_text(new_text, encoding="utf-8")
                return {"ok": True, "path": str(p), "mode": "search_replace"}

            if start_line is not None and end_line is not None:
                lines = text.splitlines()
                s = max(1, int(start_line))
                e = max(s, int(end_line))
                if s > len(lines):
                    return {"ok": False, "error_code": "line_out_of_range", "error": "line_out_of_range"}
                e = min(e, len(lines))
                repl_lines = str(replacement or "").splitlines()
                new_lines = lines[: s - 1] + repl_lines + lines[e:]
                suffix = "\n" if text.endswith("\n") else ""
                p.write_text("\n".join(new_lines) + suffix, encoding="utf-8")
                return {"ok": True, "path": str(p), "mode": "line_replace", "start_line": s, "end_line": e}
            return {"ok": False, "error_code": "invalid_edit_arguments", "error": "line_range_required"}
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}"}


_ADAPTER_SINGLETON: LocalAdapter | None = None


def get_local_adapter() -> LocalAdapter:
    global _ADAPTER_SINGLETON
    if _ADAPTER_SINGLETON is None:
        _ADAPTER_SINGLETON = LocalAdapter()
    return _ADAPTER_SINGLETON


def local_adapter_startup_self_check() -> dict[str, Any]:
    """Best-effort startup probe for local backend availability."""
    enabled = str(os.getenv("AIA_LOCAL_ADAPTER_STARTUP_SELF_CHECK") or "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not enabled:
        return {"ok": True, "enabled": False}
    try:
        adapter = LocalAdapter()
        if adapter._init_error is not None:
            return {"ok": False, "enabled": True, "error_code": adapter._init_error.error_code, "error": adapter._init_error.message}
        return {"ok": True, "enabled": True}
    except Exception as exc:
        return {
            "ok": False,
            "enabled": True,
            "error_code": "local_adapter_startup_self_check_failed",
            "error": f"{type(exc).__name__}: {exc}",
        }


__all__ = ["LocalAdapter", "LocalAdapterError", "get_local_adapter", "local_adapter_startup_self_check"]
