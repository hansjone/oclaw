from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oclaw.runtime.tools.path_guard import resolve_workspace_path, truncate_text


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
        self._cwd: str = "."

    def get_cwd(self) -> dict[str, Any]:
        try:
            p = resolve_workspace_path(self._cwd or ".")
            return {"ok": True, "cwd": str(p)}
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}"}

    def cd(self, *, cwd: str) -> dict[str, Any]:
        raw = str(cwd or "").strip()
        if not raw:
            return {"ok": False, "error_code": "cwd_required", "error": "cwd_required"}
        try:
            p = resolve_workspace_path(raw)
            if not p.exists() or not p.is_dir():
                return {"ok": False, "error_code": "not_a_directory", "error": "not_a_directory", "path": str(p)}
            # Store as workspace-relative-ish string; resolve_workspace_path handles both.
            self._cwd = str(p)
            return {"ok": True, "cwd": str(p)}
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}"}

    def get_env(self, *, key: str, default: str | None = None) -> dict[str, Any]:
        k = str(key or "").strip()
        if not k:
            return {"ok": False, "error_code": "key_required", "error": "key_required"}
        val = os.environ.get(k, default)
        return {"ok": True, "key": k, "value": val, "present": k in os.environ}

    def set_env(self, *, key: str, value: str | None = None) -> dict[str, Any]:
        k = str(key or "").strip()
        if not k:
            return {"ok": False, "error_code": "key_required", "error": "key_required"}
        if value is None:
            os.environ.pop(k, None)
            return {"ok": True, "key": k, "deleted": True}
        os.environ[k] = str(value)
        return {"ok": True, "key": k, "value": os.environ.get(k), "deleted": False}

    def run_command(self, *, command: str, cwd: str | None = None, timeout: int = 30) -> dict[str, Any]:
        cmd = str(command or "").strip()
        if not cmd:
            return {"ok": False, "error_code": "command_required", "error": "command_required"}
        try:
            timeout_s = max(1, min(int(timeout or 30), 600))
            # run_command never follows adapter cd state.
            # It only uses explicit cwd; otherwise defaults to data/workspace.
            workdir = str(resolve_workspace_path(cwd or "data/workspace"))
            Path(workdir).mkdir(parents=True, exist_ok=True)
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
            p = resolve_workspace_path(target if Path(target).is_absolute() else str(Path(self._cwd) / target))
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
            p = resolve_workspace_path(target if Path(target).is_absolute() else str(Path(self._cwd) / target))
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
            p = resolve_workspace_path(target if Path(target).is_absolute() else str(Path(self._cwd) / target))
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

    def mkdir(self, *, path: str, parents: bool = True, exist_ok: bool = True) -> dict[str, Any]:
        raw = str(path or "").strip()
        if not raw:
            return {"ok": False, "error_code": "path_required", "error": "path_required"}
        try:
            p = resolve_workspace_path(raw if Path(raw).is_absolute() else str(Path(self._cwd) / raw))
            p.mkdir(parents=bool(parents), exist_ok=bool(exist_ok))
            return {"ok": True, "path": str(p)}
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}"}

    def delete_path(self, *, path: str, missing_ok: bool = True) -> dict[str, Any]:
        raw = str(path or "").strip()
        if not raw:
            return {"ok": False, "error_code": "path_required", "error": "path_required"}
        try:
            p = resolve_workspace_path(raw if Path(raw).is_absolute() else str(Path(self._cwd) / raw))
            if not p.exists():
                return {"ok": bool(missing_ok), "path": str(p), "missing": True}
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            return {"ok": True, "path": str(p), "deleted": True}
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}"}

    def move_path(self, *, src: str, dst: str, overwrite: bool = False) -> dict[str, Any]:
        s = str(src or "").strip()
        d = str(dst or "").strip()
        if not s or not d:
            return {"ok": False, "error_code": "src_dst_required", "error": "src_dst_required"}
        try:
            p_src = resolve_workspace_path(s if Path(s).is_absolute() else str(Path(self._cwd) / s))
            p_dst = resolve_workspace_path(d if Path(d).is_absolute() else str(Path(self._cwd) / d))
            if not p_src.exists():
                return {"ok": False, "error_code": "src_not_found", "error": "src_not_found", "src": str(p_src)}
            if p_dst.exists() and not overwrite:
                return {"ok": False, "error_code": "dst_exists", "error": "dst_exists", "dst": str(p_dst)}
            p_dst.parent.mkdir(parents=True, exist_ok=True)
            if p_dst.exists() and overwrite:
                if p_dst.is_dir():
                    shutil.rmtree(p_dst)
                else:
                    p_dst.unlink()
            out = shutil.move(str(p_src), str(p_dst))
            return {"ok": True, "src": str(p_src), "dst": str(Path(out))}
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}"}

    def list_directory(self, *, path: str = ".", max_entries: int = 500) -> dict[str, Any]:
        try:
            raw = str(path or ".").strip() or "."
            p = resolve_workspace_path(raw if Path(raw).is_absolute() else str(Path(self._cwd) / raw))
            if not p.exists() or not p.is_dir():
                return {"ok": False, "error_code": "not_a_directory", "error": "not_a_directory", "path": str(p)}
            entries: list[dict[str, Any]] = []
            cap = max(1, min(int(max_entries or 500), 5000))
            for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    st = child.stat()
                except Exception:
                    continue
                mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
                entries.append(
                    {
                        "name": child.name,
                        "path": str(child),
                        "is_dir": child.is_dir(),
                        "size": int(st.st_size),
                        "mtime_utc": mtime,
                    }
                )
                if len(entries) >= cap:
                    break
            return {"ok": True, "path": str(p), "count": len(entries), "entries": entries}
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}"}

    def search_files(
        self,
        *,
        root: str = ".",
        pattern: str,
        file_glob: str = "**/*",
        regex: bool = True,
        max_matches: int = 200,
    ) -> dict[str, Any]:
        pat = str(pattern or "").strip()
        if not pat:
            return {"ok": False, "error_code": "pattern_required", "error": "pattern_required"}
        try:
            base_raw = str(root or ".").strip() or "."
            base = resolve_workspace_path(base_raw if Path(base_raw).is_absolute() else str(Path(self._cwd) / base_raw))
            if not base.exists() or not base.is_dir():
                return {"ok": False, "error_code": "not_a_directory", "error": "not_a_directory", "path": str(base)}
            rx = re.compile(pat) if regex else None
            matches: list[dict[str, Any]] = []
            cap = max(1, min(int(max_matches or 200), 5000))
            fg = str(file_glob or "**/*").strip() or "**/*"
            for p in base.glob(fg):
                if p.is_dir():
                    continue
                try:
                    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                except Exception:
                    continue
                for i, line in enumerate(lines, start=1):
                    ok = bool(rx.search(line)) if rx else (pat in line)
                    if ok:
                        matches.append({"file": str(p.relative_to(base)), "line": i, "text": line[:400]})
                        if len(matches) >= cap:
                            return {"ok": True, "root": str(base), "count": len(matches), "matches": matches}
            return {"ok": True, "root": str(base), "count": len(matches), "matches": matches}
        except re.error as exc:
            return {"ok": False, "error_code": "invalid_regex", "error": "invalid_regex", "detail": str(exc)}
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}"}

    def list_processes(self, *, max_results: int = 200) -> dict[str, Any]:
        cap = max(1, min(int(max_results or 200), 2000))
        try:
            rows: list[dict[str, Any]] = []
            if os.name == "nt":
                cp = subprocess.run(
                    "tasklist /FO CSV /NH",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10.0,
                )
                out = str(cp.stdout or "")
                for line in out.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    # "Image Name","PID","Session Name","Session#","Mem Usage"
                    parts = [p.strip().strip('"') for p in line.split('","')]
                    if len(parts) < 2:
                        continue
                    name = parts[0].strip('"')
                    pid_raw = parts[1].strip('"')
                    if pid_raw.isdigit():
                        rows.append({"pid": int(pid_raw), "name": name})
                    if len(rows) >= cap:
                        break
            else:
                cp = subprocess.run(
                    "ps -eo pid=,comm=",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10.0,
                )
                for line in str(cp.stdout or "").splitlines():
                    s = line.strip()
                    if not s:
                        continue
                    pid_str, _, name = s.partition(" ")
                    if pid_str.isdigit():
                        rows.append({"pid": int(pid_str), "name": name.strip()})
                    if len(rows) >= cap:
                        break
            return {"ok": True, "count": len(rows), "processes": rows}
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}"}

    def kill_process(self, *, pid: int, force: bool = True) -> dict[str, Any]:
        try:
            p = int(pid)
            if p <= 0:
                return {"ok": False, "error_code": "pid_invalid", "error": "pid_invalid"}
        except Exception:
            return {"ok": False, "error_code": "pid_invalid", "error": "pid_invalid"}
        try:
            if os.name == "nt":
                cmd = f"taskkill /PID {p} " + ("/F" if force else "")
                cp = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10.0)
                ok = cp.returncode == 0
                return {"ok": ok, "pid": p, "stdout": str(cp.stdout or ""), "stderr": str(cp.stderr or ""), "exit_code": int(cp.returncode)}
            import signal

            os.kill(p, signal.SIGKILL if force else signal.SIGTERM)
            return {"ok": True, "pid": p}
        except Exception as exc:
            return {"ok": False, "error_code": "local_execution_error", "error": f"{type(exc).__name__}: {exc}", "pid": p}


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
