from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oclaw.platform.config.paths import PROJECT_ROOT


_PATH_KEYS = {
    "path",
    "file",
    "dir",
    "folder",
    "input_path",
    "output_path",
    "source_path",
    "target_path",
    "workspace_path",
}

_WRITE_HINT_KEYS = {
    "output_path",
    "target_path",
    "dest_path",
    "destination_path",
    "write_path",
    "save_path",
    "out_path",
}


@dataclass(frozen=True)
class _RunResult:
    ok: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


def _resolve_allowed_roots(skill_dir: Path) -> list[Path]:
    roots = [Path(PROJECT_ROOT).resolve(), skill_dir.resolve()]
    out: list[Path] = []
    seen: set[str] = set()
    for r in roots:
        s = str(r)
        if s in seen:
            continue
        seen.add(s)
        out.append(r)
    return out


def _is_under_roots(p: Path, roots: list[Path]) -> bool:
    rp = p.resolve()
    for r in roots:
        try:
            rp.relative_to(r)
            return True
        except Exception:
            continue
    return False


def _validate_path_value(v: str, *, skill_dir: Path, roots: list[Path]) -> None:
    raw = str(v or "").strip()
    if not raw:
        return
    # Expand and resolve relative paths against skill_dir
    p = Path(raw)
    if not p.is_absolute():
        p = (skill_dir / p).resolve()
    else:
        p = p.resolve()
    if not _is_under_roots(p, roots):
        raise PermissionError(f"path_outside_allowed_roots:{raw}")


def _walk_and_validate_paths(obj: Any, *, skill_dir: Path, roots: list[Path], key_hint: str | None = None) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kk = str(k or "").strip().lower()
            _walk_and_validate_paths(v, skill_dir=skill_dir, roots=roots, key_hint=kk)
        return
    if isinstance(obj, list):
        for it in obj:
            _walk_and_validate_paths(it, skill_dir=skill_dir, roots=roots, key_hint=key_hint)
        return
    if isinstance(obj, str):
        if (key_hint or "") in _PATH_KEYS:
            _validate_path_value(obj, skill_dir=skill_dir, roots=roots)
        return


def _deny_writes_when_disabled(obj: Any, *, key_hint: str | None = None) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kk = str(k or "").strip().lower()
            _deny_writes_when_disabled(v, key_hint=kk)
        return
    if isinstance(obj, list):
        for it in obj:
            _deny_writes_when_disabled(it, key_hint=key_hint)
        return
    if isinstance(obj, str):
        if (key_hint or "") in _WRITE_HINT_KEYS and str(obj).strip():
            raise PermissionError(f"fs_write_disabled:{key_hint}")
        return


def _resolve_entry(skill_dir: Path, entry: str) -> Path:
    rel = str(entry or "").strip().replace("\\", "/")
    if not rel or rel.startswith("/") or ".." in rel.split("/"):
        raise ValueError("invalid_entry_path")
    p = (skill_dir / rel).resolve()
    try:
        p.relative_to(skill_dir.resolve())
    except Exception:
        raise ValueError("entry_outside_skill_dir")
    # If entry doesn't exist and is .ts, try .js (common in marketplace packages)
    if not p.exists() and p.suffix.lower() == ".ts":
        alt = p.with_suffix(".js")
        if alt.exists():
            return alt
    return p


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _pick_shell() -> list[str] | None:
    # Prefer explicit env override, otherwise bash then sh.
    raw = str(os.getenv("OPENCLAW_SHELL") or "").strip()
    if raw:
        exe = _which(raw)
        return [exe] if exe else None
    for c in ("bash", "sh"):
        exe = _which(c)
        if exe:
            return [exe]
    return None


def _run(argv: list[str], *, cwd: Path, stdin_json: dict[str, Any], timeout_s: float) -> _RunResult:
    import time

    start = time.time()
    p = subprocess.run(
        argv,
        input=json.dumps(stdin_json, ensure_ascii=False),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        timeout=max(1, int(timeout_s)),
        check=False,
        env=_build_env_allowlist(),
    )
    dur_ms = int((time.time() - start) * 1000)
    return _RunResult(
        ok=p.returncode == 0,
        stdout=str(p.stdout or ""),
        stderr=str(p.stderr or ""),
        exit_code=int(p.returncode),
        duration_ms=dur_ms,
    )


def _build_env_allowlist() -> dict[str, str]:
    # Minimal env for subprocesses; keep PATH for finding interpreters.
    allow = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "HOME", "USERPROFILE", "TMP", "TEMP"}
    out: dict[str, str] = {}
    for k in allow:
        v = os.environ.get(k)
        if v:
            out[k] = str(v)
    # Explicitly carry OpenAI/MCP keys? No: skills should not get host secrets by default.
    return out


def run_skill_runtime_entry(
    *,
    skill_name: str,
    skill_dir: str,
    runtime: dict[str, Any],
    args: dict[str, Any],
) -> dict[str, Any]:
    """Execute one runtime entry (shell/python/node) with restricted filesystem checks."""
    name = str(skill_name or "").strip()
    root = Path(skill_dir).resolve()
    if not root.exists() or not root.is_dir():
        return {"ok": False, "error_code": "skill_dir_missing", "error": f"skill_dir_not_found:{skill_dir}"}

    tp = str((runtime or {}).get("type") or "").strip().lower()
    entry = str((runtime or {}).get("entry") or "").strip()
    if tp not in {"shell", "python", "node"}:
        return {"ok": False, "error_code": "unsupported_runtime_type", "error": f"unsupported:{tp}"}

    try:
        entry_path = _resolve_entry(root, entry)
    except Exception as exc:
        return {"ok": False, "error_code": "invalid_entry", "error": str(exc)}
    if not entry_path.exists() or not entry_path.is_file():
        return {"ok": False, "error_code": "entry_missing", "error": f"entry_not_found:{entry}"}

    roots = _resolve_allowed_roots(root)
    perms = runtime.get("permissions") if isinstance(runtime.get("permissions"), dict) else {}
    fs_write = bool(perms.get("fs_write")) if isinstance(perms, dict) and "fs_write" in perms else False
    try:
        if not fs_write:
            _deny_writes_when_disabled(args)
        _walk_and_validate_paths(args, skill_dir=root, roots=roots)
    except PermissionError as exc:
        return {"ok": False, "error_code": "path_restricted", "error": str(exc)}

    timeout_s = float((runtime or {}).get("timeout_s") or 60.0)
    stdin_json = {"skill": name, "args": args, "permissions": {"fs_write": fs_write}}

    try:
        if tp == "python":
            argv = [sys.executable, str(entry_path)]
        elif tp == "node":
            node = _which("node")
            if not node:
                return {"ok": False, "error_code": "node_missing", "error": "node_not_found_in_PATH"}
            argv = [node, str(entry_path)]
        else:
            sh = _pick_shell()
            if not sh:
                return {"ok": False, "error_code": "shell_missing", "error": "bash_or_sh_not_found_in_PATH"}
            argv = [*sh, str(entry_path)]
        rr = _run(argv, cwd=root, stdin_json=stdin_json, timeout_s=timeout_s)
        payload: dict[str, Any] = {
            "ok": bool(rr.ok),
            "exit_code": int(rr.exit_code),
            "duration_ms": int(rr.duration_ms),
            "stdout": rr.stdout,
            "stderr": rr.stderr,
        }
        # Best-effort JSON decode for programmatic skills.
        out_obj: Any = None
        try:
            out_obj = json.loads(rr.stdout) if rr.stdout.strip().startswith(("{", "[")) else None
        except Exception:
            out_obj = None
        if out_obj is not None:
            payload["result"] = out_obj
        return payload
    except subprocess.TimeoutExpired:
        return {"ok": False, "error_code": "timeout", "error": f"timeout_s_exceeded:{timeout_s}"}
    except Exception as exc:
        return {"ok": False, "error_code": "runtime_error", "error": f"{type(exc).__name__}:{exc}"}


__all__ = ["run_skill_runtime_entry"]

