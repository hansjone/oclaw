from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from .manifest import McpServerManifest


@dataclass(frozen=True)
class McpInstallResult:
    ok: bool
    error_code: str = ""
    error: str = ""
    install_command: str = ""
    details: dict[str, Any] | None = None


def _run_command(cmd: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, Any] = {"capture_output": True, "text": True, "timeout": timeout}
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if creationflags:
            kwargs["creationflags"] = creationflags
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        kwargs["startupinfo"] = startupinfo
    return subprocess.run(cmd, **kwargs)


def _safe_server_id(seed: str) -> str:
    v = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(seed or "").strip().lower()).strip("-")
    return v or "mcp-server"


def _install_command(manifest: McpServerManifest) -> list[str]:
    def _bin(name: str) -> str:
        n = str(name or "").strip()
        if not n:
            return n
        p = shutil.which(n)
        if p:
            return p
        if os.name == "nt":
            for suffix in (".cmd", ".exe", ".bat"):
                alt = shutil.which(n + suffix)
                if alt:
                    return alt
        return n

    if manifest.source_type == "github":
        return [_bin("git"), "clone", "--depth", "1", manifest.source_ref]
    if manifest.source_type == "npm":
        pkg = manifest.source_ref + (f"@{manifest.version}" if manifest.version else "")
        return [_bin("npm"), "install", "-g", pkg]
    if manifest.source_type == "pypi":
        pkg = manifest.source_ref + (f"=={manifest.version}" if manifest.version else "")
        return [sys.executable, "-m", "pip", "install", pkg]
    raise ValueError(f"unsupported_source_type:{manifest.source_type}")


def _uninstall_command(manifest: McpServerManifest) -> list[str]:
    def _bin(name: str) -> str:
        n = str(name or "").strip()
        if not n:
            return n
        p = shutil.which(n)
        if p:
            return p
        if os.name == "nt":
            for suffix in (".cmd", ".exe", ".bat"):
                alt = shutil.which(n + suffix)
                if alt:
                    return alt
        return n

    if manifest.source_type == "npm":
        return [_bin("npm"), "uninstall", "-g", str(manifest.source_ref or "").strip()]
    if manifest.source_type == "pypi":
        return [sys.executable, "-m", "pip", "uninstall", "-y", str(manifest.source_ref or "").strip()]
    if manifest.source_type == "github":
        return []
    raise ValueError(f"unsupported_source_type:{manifest.source_type}")


def install_mcp_server(manifest: McpServerManifest, *, dry_run: bool = False) -> McpInstallResult:
    try:
        cmd = _install_command(manifest)
    except Exception as exc:
        return McpInstallResult(ok=False, error_code="mcp_invalid_source", error=str(exc))
    cmd_text = " ".join(cmd)
    if dry_run:
        return McpInstallResult(ok=True, install_command=cmd_text, details={"dry_run": True})
    try:
        cp = _run_command(cmd, timeout=180)
    except subprocess.TimeoutExpired as exc:
        return McpInstallResult(ok=False, error_code="mcp_install_timeout", error=str(exc), install_command=cmd_text)
    except FileNotFoundError as exc:
        return McpInstallResult(ok=False, error_code="mcp_installer_missing", error=str(exc), install_command=cmd_text)
    except Exception as exc:
        return McpInstallResult(ok=False, error_code="mcp_install_failed", error=str(exc), install_command=cmd_text)
    if cp.returncode != 0:
        err = (cp.stderr or cp.stdout or "").strip()
        return McpInstallResult(ok=False, error_code="mcp_install_failed", error=err[:800] or f"exit_code:{cp.returncode}", install_command=cmd_text)
    return McpInstallResult(ok=True, install_command=cmd_text, details={"stdout": (cp.stdout or "")[:800]})


def uninstall_mcp_server(manifest: McpServerManifest, *, dry_run: bool = False) -> McpInstallResult:
    try:
        cmd = _uninstall_command(manifest)
    except Exception as exc:
        return McpInstallResult(ok=False, error_code="mcp_invalid_source", error=str(exc))
    if not cmd:
        return McpInstallResult(ok=True, install_command="", details={"skipped": True, "reason": "unsupported_or_not_required"})
    cmd_text = " ".join(cmd)
    if dry_run:
        return McpInstallResult(ok=True, install_command=cmd_text, details={"dry_run": True})
    try:
        cp = _run_command(cmd, timeout=180)
    except subprocess.TimeoutExpired as exc:
        return McpInstallResult(ok=False, error_code="mcp_uninstall_timeout", error=str(exc), install_command=cmd_text)
    except FileNotFoundError as exc:
        return McpInstallResult(ok=False, error_code="mcp_installer_missing", error=str(exc), install_command=cmd_text)
    except Exception as exc:
        return McpInstallResult(ok=False, error_code="mcp_uninstall_failed", error=str(exc), install_command=cmd_text)
    if cp.returncode != 0:
        err = (cp.stderr or cp.stdout or "").strip()
        return McpInstallResult(ok=False, error_code="mcp_uninstall_failed", error=err[:800] or f"exit_code:{cp.returncode}", install_command=cmd_text)
    return McpInstallResult(ok=True, install_command=cmd_text, details={"stdout": (cp.stdout or "")[:800]})


def preflight_mcp_server(manifest: McpServerManifest) -> dict[str, Any]:
    warnings: list[str] = []
    fix_suggestions: list[dict[str, str]] = []
    entry = str(manifest.entry_command or "").strip()
    if not entry:
        return {
            "ok": False,
            "error_code": "mcp_entry_missing",
            "error": "entry_command_missing",
            "warnings": warnings,
            "fix_suggestions": [{"title": "Set entry command", "command": "npx <pkg> | python -m <module> | node <script.js>"}],
        }
    found = shutil.which(entry)
    if not found:
        if entry in {"npx", "npm", "node"}:
            fix_suggestions.append({"title": "Install Node.js", "command": "https://nodejs.org/en/download"})
        elif entry in {"python", "pip"}:
            fix_suggestions.append({"title": "Install Python", "command": "https://www.python.org/downloads/"})
        elif entry == "git":
            fix_suggestions.append({"title": "Install Git", "command": "https://git-scm.com/downloads"})
        else:
            fix_suggestions.append({"title": "Check PATH", "command": f"where {entry}"})
        return {"ok": False, "error_code": "mcp_entry_not_found", "error": f"entry_command_not_found:{entry}", "warnings": warnings, "fix_suggestions": fix_suggestions}
    env_schema = manifest.env_schema if isinstance(manifest.env_schema, dict) else {}
    required_env = [str(k) for k, v in env_schema.items() if isinstance(v, dict) and bool(v.get("required"))]
    return {"ok": True, "error_code": "", "error": "", "entry_command_path": found, "required_env": required_env, "warnings": warnings, "fix_suggestions": fix_suggestions}


def detect_local_dependencies() -> list[dict[str, Any]]:
    deps = [{"name": "git", "version_args": ["--version"]}, {"name": "node", "version_args": ["--version"]}, {"name": "npm", "version_args": ["--version"]}, {"name": "npx", "version_args": ["--version"]}, {"name": "python", "version_args": ["--version"]}, {"name": "pip", "version_args": ["--version"]}]
    out: list[dict[str, Any]] = []
    for d in deps:
        name = str(d["name"])
        path = shutil.which(name)
        if not path:
            out.append({"name": name, "ok": False, "path": "", "version": ""})
            continue
        ver = ""
        try:
            cp = _run_command([name] + list(d["version_args"]), timeout=4)
            ver = (cp.stdout or cp.stderr or "").strip().splitlines()[0] if (cp.stdout or cp.stderr) else ""
        except Exception:
            ver = ""
        out.append({"name": name, "ok": True, "path": path, "version": ver})
    return out


__all__ = ["McpInstallResult", "install_mcp_server", "uninstall_mcp_server", "preflight_mcp_server", "detect_local_dependencies", "_safe_server_id"]
