from __future__ import annotations

from typing import Any


def resolve_channel_account_ui_owner(
    store: Any,
    *,
    channel: str,
    account_id: str,
    tenant_id: str,
    fallback_user_id: str = "",
) -> tuple[str, str]:
    """UI list owner for channel-derived sessions: the oclaw user who owns the channel account."""
    acct = store.find_user_by_channel_account(channel=str(channel or ""), account_id=str(account_id or "")) or {}
    owner_tid = str(acct.get("tenant_id") or tenant_id or "").strip()
    owner_uid = str(acct.get("user_id") or "").strip()
    if owner_uid:
        return owner_tid, owner_uid
    admin = store.get_user_by_username(tenant_id=owner_tid or tenant_id, username="administrator")
    if isinstance(admin, dict):
        owner_uid = str(admin.get("id") or "").strip()
        owner_tid = str(admin.get("tenant_id") or owner_tid or tenant_id).strip()
    if owner_uid:
        return owner_tid, owner_uid
    return str(tenant_id or "").strip(), str(fallback_user_id or "").strip()


def assign_channel_session_to_account_owner(
    store: Any,
    *,
    session_id: str,
    channel: str,
    account_id: str,
    tenant_id: str,
    fallback_user_id: str = "",
) -> None:
    owner_tid, owner_uid = resolve_channel_account_ui_owner(
        store,
        channel=channel,
        account_id=account_id,
        tenant_id=tenant_id,
        fallback_user_id=fallback_user_id,
    )
    if not owner_tid or not owner_uid:
        return
    setter = getattr(store, "set_ui_session_owner", None)
    if callable(setter):
        setter(session_id=str(session_id), tenant_id=owner_tid, user_id=owner_uid)
        return
    store.ensure_ui_session_owner(session_id=str(session_id), tenant_id=owner_tid, user_id=owner_uid)


__all__ = [
    "assign_channel_session_to_account_owner",
    "resolve_channel_account_ui_owner",
]
