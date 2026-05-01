"""Augment MCP @modelcontextprotocol/server-filesystem argv with extra allowed directories.

The filesystem MCP only exposes directories passed on the command line at process start.
Gateway workspace policy (env + per-user DB) must be mirrored here so list_directory sees the same roots.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _split_pipe_paths(raw: str) -> list[str]:
    out: list[str] = []
    for part in (raw or "").split("|"):
        s = part.strip().strip('"').strip("'")
        if s:
            out.append(s)
    return out


def _dedup_key(p: str) -> str:
    """Stable key for deduplicating directory roots (Windows: case-insensitive)."""
    ra = _resolved_abs_for_argv(p)
    if not ra:
        return ""
    if os.name == "nt":
        return os.path.normcase(ra)
    return ra


def _resolved_abs_for_argv(p: str) -> str:
    """Absolute path string suitable for MCP process argv; avoids silent drop on resolve quirks."""
    raw = (p or "").strip().strip('"').strip("'")
    if not raw:
        return ""
    try:
        exp = Path(raw).expanduser()
        s = str(exp.resolve())
        if s:
            return s
    except (OSError, ValueError, RuntimeError):
        pass
    try:
        return os.path.normpath(os.path.abspath(raw))
    except Exception:
        return ""


def _allowlist_extras_tenant_user(*, store: Any, tenant_id: str, user_id: str) -> list[str]:
    t = (tenant_id or "").strip()
    u = (user_id or "").strip()
    if not t or not u or store is None:
        return []
    try:
        row = store.get_user_workspace_path_allowlist(tenant_id=t, user_id=u)
    except Exception:
        return []
    if not row or not isinstance(row, dict):
        return []
    out: list[str] = []
    for s in _split_pipe_paths(str(row.get("extra_roots") or "")):
        if s:
            out.append(s)
    return out


def _extra_roots_for_policy_session(*, store: Any, policy_session_id: str) -> list[str]:
    """Per-user ``extra_roots`` from DB for the chat session that owns the tool run (not a global union)."""
    out: list[str] = []
    sid = str(policy_session_id or "").strip()
    if not sid:
        return out
    try:
        own = store.get_ui_session_owner(session_id=sid)
    except Exception:
        own = None
    if not own:
        return out
    tid = str(own.get("tenant_id") or "").strip()
    uid = str(own.get("user_id") or "").strip()
    if not tid or not uid:
        return out
    try:
        row = store.get_user_workspace_path_allowlist(tenant_id=tid, user_id=uid)
    except Exception:
        row = None
    if not row:
        return out
    for s in _split_pipe_paths(str(row.get("extra_roots") or "")):
        if s:
            out.append(s)
    return out


def collect_filesystem_mcp_extra_roots(
    *,
    store: Any | None,
    policy_session_id: str | None = None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
) -> list[str]:
    """Paths to append to server-filesystem argv (deduped after resolve).

    Per-user roots from SQLite only when ``policy_session_id`` resolves via
    ``ui_session_owner`` (typically the user's chat session id). Without it, only
    env/settings roots are merged (safe for admin Health/Sync and shared agents).
    You may also pass ``path_policy_tenant_id`` / ``path_policy_user_id`` to mirror
    the same allowlist when the request ``metadata`` carries the effective user, but
    ``ui_session_owner`` is not yet set (e.g. legacy data).
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in (
        str(os.getenv("AIA_WORKSPACE_EXTRA_ROOTS") or os.getenv("OPS_WORKSPACE_EXTRA_ROOTS") or "").strip(),
        str(os.getenv("AIA_MCP_FILESYSTEM_EXTRA_ROOTS") or os.getenv("OPS_MCP_FILESYSTEM_EXTRA_ROOTS") or "").strip(),
    ):
        for s in _split_pipe_paths(raw):
            dk = _dedup_key(s)
            ra = _resolved_abs_for_argv(s)
            if dk and ra and dk not in seen:
                seen.add(dk)
                ordered.append(ra)
    if store is not None:
        try:
            raw2 = str(store.get_setting("AIA_MCP_FILESYSTEM_EXTRA_ROOTS") or "").strip()
            for s in _split_pipe_paths(raw2):
                dk = _dedup_key(s)
                ra = _resolved_abs_for_argv(s)
                if dk and ra and dk not in seen:
                    seen.add(dk)
                    ordered.append(ra)
        except Exception:
            pass
        ps = str(policy_session_id or "").strip()
        if ps:
            try:
                for s in _extra_roots_for_policy_session(store=store, policy_session_id=ps):
                    dk = _dedup_key(s)
                    ra = _resolved_abs_for_argv(s)
                    if dk and ra and dk not in seen:
                        seen.add(dk)
                        ordered.append(ra)
            except Exception:
                pass
        t_id = (path_policy_tenant_id or "").strip()
        u_id = (path_policy_user_id or "").strip()
        if t_id and u_id and store is not None:
            try:
                for s in _allowlist_extras_tenant_user(store=store, tenant_id=t_id, user_id=u_id):
                    dk = _dedup_key(s)
                    ra = _resolved_abs_for_argv(s)
                    if dk and ra and dk not in seen:
                        seen.add(dk)
                        ordered.append(ra)
            except Exception:
                pass
    return ordered


def is_modelcontext_filesystem_command(command: list[str]) -> bool:
    return any("server-filesystem" in str(x) for x in command)


def augment_filesystem_mcp_argv(
    command: list[str],
    *,
    store: Any | None,
    policy_session_id: str | None = None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
) -> list[str]:
    """
    If ``command`` starts the official Model Context Protocol filesystem server, append
    extra directory roots from env / settings / DB so tools/list and tools/call match gateway policy.
    """
    if not command or not is_modelcontext_filesystem_command(command):
        return command
    extras = collect_filesystem_mcp_extra_roots(
        store=store,
        policy_session_id=policy_session_id,
        path_policy_tenant_id=path_policy_tenant_id,
        path_policy_user_id=path_policy_user_id,
    )
    if not extras:
        return command
    existing: set[str] = set()
    for p in command:
        s = str(p).strip()
        if not s or s.startswith("-") or "server-filesystem" in s:
            continue
        if s in ("npx", "pnpm", "yarn", "uvx", "bun"):
            continue
        dk = _dedup_key(s)
        if dk:
            existing.add(dk)
    out = list(command)
    for extra_abs in extras:
        dk = _dedup_key(extra_abs)
        if dk and dk not in existing:
            out.append(extra_abs)
            existing.add(dk)
    return out


def build_mcp_process_command(
    cmd: str,
    args: list[str],
    *,
    store: Any | None,
    policy_session_id: str | None = None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
) -> list[str]:
    """``[cmd] + args`` after env placeholder expansion + filesystem argv augmentation."""
    base = [str(cmd)]
    for x in args:
        s = str(x).strip()
        if not s:
            continue
        # Allow mcp entry args like: "Authorization: Bearer ${DASHSCOPE_API_KEY}".
        # Unknown vars are kept unchanged by expandvars.
        base.append(os.path.expandvars(s))
    return augment_filesystem_mcp_argv(
        base,
        store=store,
        policy_session_id=policy_session_id,
        path_policy_tenant_id=path_policy_tenant_id,
        path_policy_user_id=path_policy_user_id,
    )


__all__ = [
    "augment_filesystem_mcp_argv",
    "build_mcp_process_command",
    "collect_filesystem_mcp_extra_roots",
    "is_modelcontext_filesystem_command",
]
