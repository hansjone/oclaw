from __future__ import annotations

from typing import Any

_CONTEXT_SCOPED_TOOL_PREFIXES = ("schedule_", "todo_")
_CONTEXT_SCOPED_TOOL_NAMES = frozenset(
    {
        "kb_add",
        "kb_search",
    }
)


def _session_owner(store: Any, session_id: str) -> tuple[str, str]:
    sid = str(session_id or "").strip()
    if not sid:
        return "", ""
    try:
        owner = store.get_ui_session_owner(session_id=sid) or {}
    except Exception:
        owner = {}
    if isinstance(owner, dict):
        tid = str(owner.get("tenant_id") or "").strip()
        uid = str(owner.get("user_id") or "").strip()
        if tid and uid:
            return tid, uid
    return "", ""


def enrich_tool_arguments(
    *,
    store: Any,
    session_id: str,
    tool_name: str,
    arguments: dict[str, Any] | None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
) -> dict[str, Any]:
    """Inject tenant/user/session context for productivity tools (WeChat, WhatsApp, etc.)."""
    merged = dict(arguments or {})
    name = str(tool_name or "").strip()
    if not name:
        return merged
    scoped = name in _CONTEXT_SCOPED_TOOL_NAMES or any(
        name.startswith(p) for p in _CONTEXT_SCOPED_TOOL_PREFIXES
    )
    if not scoped:
        return merged

    tenant_id = str(path_policy_tenant_id or merged.get("tenant_id") or "").strip()
    user_id = str(path_policy_user_id or merged.get("owner_user_id") or merged.get("user_id") or "").strip()
    if not tenant_id or not user_id:
        o_tid, o_uid = _session_owner(store, session_id)
        tenant_id = tenant_id or o_tid
        user_id = user_id or o_uid

    if tenant_id:
        merged["tenant_id"] = tenant_id
    if user_id:
        if name in _CONTEXT_SCOPED_TOOL_NAMES:
            merged["user_id"] = user_id
        else:
            merged["owner_user_id"] = user_id
    sid = str(session_id or merged.get("session_id") or "").strip()
    if sid:
        merged["session_id"] = sid
    return merged


__all__ = ["enrich_tool_arguments"]
