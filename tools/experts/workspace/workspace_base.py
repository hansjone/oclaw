from __future__ import annotations

import os
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from oclaw.platform.config.paths import PROJECT_ROOT

_TLS = threading.local()


def _env_truthy(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def workspace_root() -> Path:
    # Allow explicit override (recommended when running as a packaged app)
    override = (os.getenv("AIA_WORKSPACE_ROOT") or os.getenv("OPS_WORKSPACE_ROOT") or "").strip()
    if override:
        p = Path(override).expanduser()
        return p.resolve()
    return Path(PROJECT_ROOT).resolve()


def _parse_pipe_separated_roots(raw: str) -> list[Path]:
    out: list[Path] = []
    for part in (raw or "").split("|"):
        p = part.strip().strip('"').strip("'")
        if not p:
            continue
        try:
            rp = Path(p).expanduser().resolve()
            if rp.is_absolute():
                out.append(rp)
        except Exception:
            continue
    return out


@dataclass(frozen=True)
class WorkspacePathAccess:
    """Effective path guard for the current tool invocation (env + optional per-user DB)."""

    extra_roots: tuple[Path, ...]
    allow_any_path: bool


def access_from_env() -> WorkspacePathAccess:
    raw_extra = os.getenv("AIA_WORKSPACE_EXTRA_ROOTS") or os.getenv("OPS_WORKSPACE_EXTRA_ROOTS") or ""
    extra = _parse_pipe_separated_roots(raw_extra)
    allow = _env_truthy("AIA_WORKSPACE_ALLOW_ANY_PATH") or _env_truthy("OPS_WORKSPACE_ALLOW_ANY_PATH")
    return WorkspacePathAccess(extra_roots=tuple(extra), allow_any_path=allow)


def _merge_access(a: WorkspacePathAccess, b: WorkspacePathAccess) -> WorkspacePathAccess:
    merged: dict[str, Path] = {}
    for p in (*a.extra_roots, *b.extra_roots):
        try:
            k = str(p.resolve())
        except Exception:
            k = str(p)
        merged.setdefault(k, p)
    return WorkspacePathAccess(
        extra_roots=tuple(merged.values()),
        allow_any_path=bool(a.allow_any_path or b.allow_any_path),
    )


def build_workspace_path_access(
    store: Any,
    session_id: str | None,
    *,
    owner_fallback_session_id: str | None = None,
    allowlist_tenant_id: str | None = None,
    allowlist_user_id: str | None = None,
) -> WorkspacePathAccess:
    """Resolve per-user ``extra_roots`` / ``allow_any_path`` from ``user_workspace_path_allowlist``.

    ``session_id`` is usually the chat row messages are written to (may be a specialist temp session
    without ``ui_session_owner``). In that case pass ``owner_fallback_session_id`` = the user's
    UI-owned session id so DB allowlist still applies.

    If ``get_ui_session_owner`` yields nothing, ``allowlist_tenant_id`` + ``allowlist_user_id``
    (from the authenticated user / request metadata) can be used to load the same allowlist, so
    a missing ``ui_session_owner`` row does not drop per-user extra roots.
    """
    base = access_from_env()
    if store is None:
        return base

    picked_owner: dict[str, Any] | None = None
    for cand in (str(session_id or "").strip(), str(owner_fallback_session_id or "").strip()):
        if not cand:
            continue
        try:
            own = store.get_ui_session_owner(session_id=cand)
        except Exception:
            own = None
        if not own:
            continue
        tid = str(own.get("tenant_id") or "").strip()
        uid = str(own.get("user_id") or "").strip()
        if tid and uid:
            picked_owner = own
            break

    if picked_owner:
        tid = str(picked_owner.get("tenant_id") or "").strip()
        uid = str(picked_owner.get("user_id") or "").strip()
        try:
            row = store.get_user_workspace_path_allowlist(tenant_id=tid, user_id=uid)
        except Exception:
            row = None
        if not row:
            return base
        db_extras = _parse_pipe_separated_roots(str(row.get("extra_roots") or ""))
        db_access = WorkspacePathAccess(
            extra_roots=tuple(db_extras),
            allow_any_path=bool(row.get("allow_any_path")),
        )
        return _merge_access(base, db_access)

    # Fallback: use explicit tenant / user (e.g. wecom or admin ``metadata``) when session is not
    # linked in ``ui_session_owner`` (legacy session or data repair in progress).
    t2 = str(allowlist_tenant_id or "").strip()
    u2 = str(allowlist_user_id or "").strip()
    if not t2 or not u2:
        return base
    try:
        row = store.get_user_workspace_path_allowlist(tenant_id=t2, user_id=u2)
    except Exception:
        row = None
    if not row:
        return base
    db_extras = _parse_pipe_separated_roots(str(row.get("extra_roots") or ""))
    db_access = WorkspacePathAccess(
        extra_roots=tuple(db_extras),
        allow_any_path=bool(row.get("allow_any_path")),
    )
    return _merge_access(base, db_access)


@contextmanager
def workspace_path_access_scope(
    store: Any,
    session_id: str | None,
    *,
    owner_fallback_session_id: str | None = None,
    allowlist_tenant_id: str | None = None,
    allowlist_user_id: str | None = None,
) -> Iterator[WorkspacePathAccess]:
    acc = build_workspace_path_access(
        store,
        session_id,
        owner_fallback_session_id=owner_fallback_session_id,
        allowlist_tenant_id=allowlist_tenant_id,
        allowlist_user_id=allowlist_user_id,
    )
    prev = getattr(_TLS, "access", None)
    _TLS.access = acc
    try:
        yield acc
    finally:
        if prev is None:
            if hasattr(_TLS, "access"):
                delattr(_TLS, "access")
        else:
            _TLS.access = prev


def current_workspace_path_access() -> WorkspacePathAccess:
    a = getattr(_TLS, "access", None)
    if isinstance(a, WorkspacePathAccess):
        return a
    return access_from_env()


def clear_workspace_path_access_for_tests() -> None:
    if hasattr(_TLS, "access"):
        delattr(_TLS, "access")


def _is_subpath(path: Path, root: Path) -> bool:
    """``path`` is under ``root`` (treated as a directory), including the root itself.

    On Windows, comparison is case- and path-separator-insensitive; ``resolve`` may
    not normalize casing consistently across all drives, so we use normcase.
    """
    try:
        pr = path.resolve()
        rr = root.resolve()
    except (OSError, ValueError, RuntimeError):
        return False
    if os.name == "nt":
        np = os.path.normcase(str(pr))
        nroot = os.path.normcase(str(rr))
        if np == nroot:
            return True
        sep = os.sep
        if not nroot.endswith(sep):
            nroot = nroot + sep
        return np.startswith(nroot) or (np + sep).startswith(nroot)
    try:
        pr.relative_to(rr)
        return True
    except (ValueError, OSError, RuntimeError):
        return False


def resolve_workspace_path(user_path: str) -> Path:
    p = Path(str(user_path or "").strip().strip('"').strip("'") or "")
    if not p:
        raise ValueError("path is required")
    root = workspace_root()
    abs_path = p if p.is_absolute() else (root / p)
    abs_path = abs_path.resolve()
    access = current_workspace_path_access()
    if access.allow_any_path:
        return abs_path
    roots = (root,) + access.extra_roots
    if any(_is_subpath(abs_path, r) for r in roots):
        return abs_path
    raise ValueError("path escapes workspace root")


def truncate_text(s: str, *, limit: int = 20000) -> str:
    s = s or ""
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 12)] + "\n...<truncated>"


# NOTE: put '-' at end or escape it to avoid "bad character range" on Windows Python regex.
_SAFE_GIT_REF_RE = re.compile(r"^[A-Za-z0-9._/\\-]{1,80}$")


def sanitize_git_ref(ref: str) -> str:
    r = (ref or "").strip()
    if not r:
        return ""
    if not _SAFE_GIT_REF_RE.match(r):
        raise ValueError("invalid git ref")
    return r


__all__ = [
    "WorkspacePathAccess",
    "access_from_env",
    "build_workspace_path_access",
    "clear_workspace_path_access_for_tests",
    "current_workspace_path_access",
    "resolve_workspace_path",
    "sanitize_git_ref",
    "truncate_text",
    "workspace_path_access_scope",
    "workspace_root",
]
