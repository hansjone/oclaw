from __future__ import annotations

import subprocess
from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.experts.workspace.workspace_base import resolve_workspace_path, truncate_text, sanitize_git_ref


def _git(command: str, *, cwd: str) -> dict[str, Any]:
    workdir = resolve_workspace_path(cwd or ".")
    cp = subprocess.run(
        f"git {command}",
        cwd=str(workdir),
        shell=True,
        capture_output=True,
        text=True,
        timeout=60.0,
    )
    out = (cp.stdout or "") + (("\n" + cp.stderr) if cp.stderr else "")
    return {"exit_code": int(cp.returncode), "output": truncate_text(out, limit=20000), "cwd": str(workdir)}


def git_status_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        cwd = str(args.get("cwd") or ".").strip()
        res = _git("status --porcelain=v1 -b", cwd=cwd)
        ok = res["exit_code"] == 0
        return {"ok": ok, **res}

    return ToolSpec(
        name="git_status",
        description="Show git status (porcelain).",
        parameters={
            "type": "object",
            "properties": {"cwd": {"type": "string", "default": ".", "description": "Repo directory."}},
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"workspace", "git"}),
    )


def git_diff_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        cwd = str(args.get("cwd") or ".").strip()
        ref = sanitize_git_ref(str(args.get("ref") or "").strip()) if args.get("ref") else ""
        cmd = "diff" if not ref else f"diff {ref}...HEAD"
        res = _git(cmd, cwd=cwd)
        ok = res["exit_code"] == 0
        return {"ok": ok, **res}

    return ToolSpec(
        name="git_diff",
        description="Show git diff (default: working tree; optional ref...HEAD).",
        parameters={
            "type": "object",
            "properties": {
                "cwd": {"type": "string", "default": ".", "description": "Repo directory."},
                "ref": {"type": "string", "description": "Optional ref for ref...HEAD diff."},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"workspace", "git"}),
    )


def git_log_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        cwd = str(args.get("cwd") or ".").strip()
        n = int(args.get("n") or 10)
        n = max(1, min(n, 50))
        res = _git(f"log -{n} --oneline --decorate", cwd=cwd)
        ok = res["exit_code"] == 0
        return {"ok": ok, **res}

    return ToolSpec(
        name="git_log",
        description="Show recent git commits (oneline).",
        parameters={
            "type": "object",
            "properties": {"cwd": {"type": "string", "default": ".", "description": "Repo directory."}, "n": {"type": "integer", "default": 10}},
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"workspace", "git"}),
    )


def git_commit_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        cwd = str(args.get("cwd") or ".").strip()
        message = str(args.get("message") or "").strip()
        if not message:
            return {"ok": False, "error": "message_required"}
        # stage all changes (simple default)
        s1 = _git("add -A", cwd=cwd)
        if s1["exit_code"] != 0:
            return {"ok": False, "error": "git_add_failed", **s1}
        msg_esc = message.replace('"', '\\"')
        s2 = _git(f'commit -m "{msg_esc}"', cwd=cwd)
        ok = s2["exit_code"] == 0
        return {"ok": ok, **s2}

    return ToolSpec(
        name="git_commit",
        description="Stage all and create a git commit (requires confirmation by policy).",
        parameters={
            "type": "object",
            "properties": {
                "cwd": {"type": "string", "default": ".", "description": "Repo directory."},
                "message": {"type": "string", "description": "Commit message."},
            },
            "required": ["message"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"workspace", "git", "write"}),
    )


def git_push_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        cwd = str(args.get("cwd") or ".").strip()
        remote = str(args.get("remote") or "origin").strip() or "origin"
        refspec = str(args.get("refspec") or "HEAD").strip() or "HEAD"
        res = _git(f"push {remote} {refspec}", cwd=cwd)
        ok = res["exit_code"] == 0
        return {"ok": ok, **res}

    return ToolSpec(
        name="git_push",
        description="Push current branch (requires confirmation by policy).",
        parameters={
            "type": "object",
            "properties": {
                "cwd": {"type": "string", "default": ".", "description": "Repo directory."},
                "remote": {"type": "string", "default": "origin"},
                "refspec": {"type": "string", "default": "HEAD"},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"workspace", "git", "write"}),
    )


__all__ = ["git_status_tool", "git_diff_tool", "git_log_tool", "git_commit_tool", "git_push_tool"]

