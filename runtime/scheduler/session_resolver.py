from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from runtime.orchestration.group_ingest import session_user_key


@dataclass(frozen=True)
class ResolvedSession:
    session_id: str
    tenant_id: str
    user_id: str
    channel: str
    account_id: str
    external_chat_id: str
    external_user_id: str
    is_group: bool
    source_session_id: str = ""


def _ensure_administrator_owner(store: Any, *, tenant_id: str) -> dict[str, Any] | None:
    user = store.get_user_by_username(tenant_id=tenant_id, username="administrator")
    if not user:
        try:
            from svc.config.passwords import load_expected_password
        except Exception:
            load_expected_password = None  # type: ignore
        pwd = load_expected_password(store) if callable(load_expected_password) else None
        if not pwd:
            return None
        user = store.create_user_account(
            tenant_id=tenant_id,
            username="administrator",
            password_hash=hashlib.sha256(pwd.encode("utf-8")).hexdigest(),
            display_name="Administrator",
            role="owner",
            is_active=True,
        )
    user_id = str((user or {}).get("id") or "")
    if not user_id:
        return None
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "display_name": (user or {}).get("display_name") or "Administrator",
        "role": str((user or {}).get("role") or "owner"),
    }


def _create_scheduled_execution_session(
    store: Any,
    *,
    tenant_id: str,
    user_id: str,
    job_name: str,
    run_id: str = "",
) -> str:
    rid = str(run_id or "").strip()
    title = f"Scheduled · {job_name}"
    if rid:
        title = f"{title} · {rid[:8]}"
    tid = str(tenant_id or "").strip()
    uid = str(user_id or "").strip()
    if uid and tid:
        sess = store.create_session_for_user(title=title, tenant_id=tid, user_id=uid)
    else:
        sess = store.create_session(title)
    return str(sess.id)


def _resolve_scheduled_channel_context(
    store: Any,
    *,
    job: Any,
    created_by_user_id: str = "",
) -> tuple[str, str, str, str, str, str, bool, str]:
    """Return tenant_id, user_id, channel, account_id, external_chat_id, external_user_id, is_group, source_session_id."""
    tenant_id = str(getattr(job, "tenant_id", "") or "")
    delivery = parse_delivery_json(str(getattr(job, "delivery_json", "") or "{}"))
    source_session_id = str(getattr(job, "source_session_id", "") or "").strip()

    if source_session_id:
        sess = store.get_session_in_tenant(session_id=source_session_id, tenant_id=tenant_id)
        if sess:
            owner = store.get_ui_session_owner(session_id=source_session_id) or {}
            user_id = str(owner.get("user_id") or created_by_user_id or "").strip()
            if not user_id:
                admin = _ensure_administrator_owner(store, tenant_id=tenant_id)
                user_id = str((admin or {}).get("user_id") or "")
            channel_ctx = None
            lookup = getattr(store, "lookup_channel_session_by_session_id", None)
            if callable(lookup):
                channel_ctx = lookup(tenant_id=tenant_id, session_id=source_session_id)
            if isinstance(channel_ctx, dict) and str(channel_ctx.get("channel") or "").strip():
                ch = str(channel_ctx.get("channel") or "").strip().lower()
                account_id = str(channel_ctx.get("account_id") or "").strip()
                external_chat_id = str(channel_ctx.get("external_chat_id") or "").strip()
                external_user_id = str(channel_ctx.get("external_user_id") or "").strip()
                is_group = ch == "whatsapp" and external_chat_id.endswith("@g.us")
                return (
                    tenant_id,
                    user_id,
                    ch,
                    account_id or ("weixin-default" if ch in {"weixin", "wechat"} else ""),
                    external_chat_id,
                    external_user_id,
                    is_group,
                    source_session_id,
                )
            return (
                tenant_id,
                user_id,
                "admin_chat",
                "",
                "",
                "",
                False,
                source_session_id,
            )

    wa = delivery.get("whatsapp") if isinstance(delivery.get("whatsapp"), dict) else {}
    wx = delivery.get("weixin") if isinstance(delivery.get("weixin"), dict) else {}
    wa_enabled = bool(wa.get("enabled")) and str(wa.get("target_type") or "none") != "none"
    wx_enabled = bool(wx.get("enabled", True))

    if wa_enabled and str(wa.get("chat_id") or "").strip():
        chat_id = str(wa.get("chat_id") or "").strip()
        account_id = str(wa.get("account_id") or os.getenv("AIA_WHATSAPP_ACCOUNT_ID") or "wa-default").strip()
        target_type = str(wa.get("target_type") or "direct").strip().lower()
        is_group = target_type == "group" or chat_id.endswith("@g.us")
        external_user_id = session_user_key(is_group=is_group, external_user_id=chat_id.split("@", 1)[0])
        admin = _ensure_administrator_owner(store, tenant_id=tenant_id)
        user_id = str(created_by_user_id or (admin or {}).get("user_id") or "")
        return (
            tenant_id,
            user_id,
            "whatsapp",
            account_id,
            chat_id,
            external_user_id,
            is_group,
            "",
        )

    if wx_enabled:
        binding = resolve_weixin_binding(store, tenant_id=tenant_id)
        if not binding:
            raise RuntimeError("weixin_binding_missing")
        channel = str(binding.get("channel") or "weixin")
        account_id = str(binding.get("account_id") or "weixin-default")
        external_user_id = str(binding.get("external_user_id") or "")
        external_chat_id = str(binding.get("external_chat_id") or external_user_id)
        user_id = str(binding.get("user_id") or created_by_user_id or "")
        return (
            tenant_id,
            user_id,
            channel,
            account_id,
            external_chat_id,
            external_user_id,
            False,
            "",
        )

    admin = _ensure_administrator_owner(store, tenant_id=tenant_id)
    user_id = str(created_by_user_id or (admin or {}).get("user_id") or "")
    if not user_id:
        raise RuntimeError("scheduled_session_owner_missing")
    return (
        tenant_id,
        user_id,
        "admin_chat",
        "",
        "",
        "",
        False,
        source_session_id,
    )


def resolve_weixin_binding(store: Any, *, tenant_id: str) -> dict[str, Any] | None:
    owner = _ensure_administrator_owner(store, tenant_id=tenant_id)
    if not owner:
        return None
    user_id = str(owner.get("user_id") or "")
    rows = store.list_channel_identities_v2(
        tenant_id=tenant_id,
        channel="weixin",
        user_id=user_id,
        limit=20,
    )
    if not rows:
        for ch in ("wechat", "weixin"):
            rows = store.list_channel_identities_v2(
                tenant_id=tenant_id,
                channel=ch,
                user_id=user_id,
                limit=20,
            )
            if rows:
                break
    if not rows:
        return None
    row = rows[0]
    account_id = str(row.get("account_id") or "weixin-default").strip() or "weixin-default"
    external_user_id = str(row.get("external_user_id") or "").strip()
    if not external_user_id:
        return None
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "channel": str(row.get("channel") or "weixin"),
        "account_id": account_id,
        "external_user_id": external_user_id,
        "external_chat_id": external_user_id,
        "is_group": False,
    }


def parse_delivery_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def resolve_scheduled_viewer_username(
    store: Any,
    *,
    tenant_id: str,
    user_id: str,
    channel: str,
) -> str:
    """Channel proactive jobs use the administrator model pool (same as gateway inbound)."""
    ch = str(channel or "").strip().lower()
    if ch in {"weixin", "wechat", "whatsapp"}:
        return "administrator"
    uid = str(user_id or "").strip()
    if uid:
        user = store.get_user_by_id(tenant_id=str(tenant_id or ""), user_id=uid)
        if isinstance(user, dict):
            uname = str(user.get("username") or "").strip()
            if uname:
                return uname
    return "administrator"


def resolve_scheduled_session(
    store: Any,
    *,
    job: Any,
    created_by_user_id: str = "",
    run_id: str = "",
) -> ResolvedSession:
    job_name = str(getattr(job, "name", "") or "Scheduled task")
    (
        tenant_id,
        user_id,
        channel,
        account_id,
        external_chat_id,
        external_user_id,
        is_group,
        source_session_id,
    ) = _resolve_scheduled_channel_context(
        store,
        job=job,
        created_by_user_id=created_by_user_id,
    )
    execution_session_id = _create_scheduled_execution_session(
        store,
        tenant_id=tenant_id,
        user_id=user_id,
        job_name=job_name,
        run_id=run_id,
    )
    return ResolvedSession(
        session_id=execution_session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        channel=channel,
        account_id=account_id,
        external_chat_id=external_chat_id,
        external_user_id=external_user_id,
        is_group=is_group,
        source_session_id=source_session_id,
    )


__all__ = [
    "ResolvedSession",
    "resolve_scheduled_session",
    "resolve_scheduled_viewer_username",
    "resolve_weixin_binding",
    "parse_delivery_json",
]
