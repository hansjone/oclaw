from __future__ import annotations

from typing import Any

from runtime.scheduler.session_resolver import resolve_weixin_binding


def normalize_weixin_channel(channel: str) -> str:
    ch = str(channel or "wechat").strip().lower()
    return "wechat" if ch in {"wechat", "weixin"} else ch


def resolve_weixin_delivery_target(
    store: Any,
    *,
    tenant_id: str,
    session_id: str,
    delivery: dict[str, Any],
    resolved_channel: str,
    resolved_chat_id: str,
    resolved_account_id: str,
) -> dict[str, Any]:
    wx = delivery.get("weixin") if isinstance(delivery.get("weixin"), dict) else {}
    channel = normalize_weixin_channel(
        str(resolved_channel or wx.get("channel") or "wechat")
    )
    chat_id = str(
        resolved_chat_id or wx.get("external_chat_id") or wx.get("external_user_id") or ""
    ).strip()
    account_id = str(
        resolved_account_id or wx.get("account_id") or ""
    ).strip()

    sid = str(session_id or "").strip()
    lookup_sess = getattr(store, "lookup_channel_session_by_session_id", None)
    if sid and callable(lookup_sess):
        ctx = lookup_sess(tenant_id=str(tenant_id or ""), session_id=sid)
        if isinstance(ctx, dict):
            if not chat_id:
                chat_id = str(ctx.get("external_chat_id") or ctx.get("external_user_id") or "").strip()
            if not account_id or account_id == "weixin-default":
                account_id = str(ctx.get("account_id") or account_id or "").strip()
            if channel in {"wechat", "weixin"}:
                channel = normalize_weixin_channel(str(ctx.get("channel") or channel))

    lookup_chat = getattr(store, "lookup_channel_session_by_chat_v2", None)
    if chat_id and callable(lookup_chat) and (not account_id or account_id == "weixin-default"):
        ctx = lookup_chat(
            tenant_id=str(tenant_id or ""),
            channel=channel,
            external_chat_id=chat_id,
        )
        if isinstance(ctx, dict):
            acct = str(ctx.get("account_id") or "").strip()
            if acct:
                account_id = acct

    if not chat_id:
        binding = resolve_weixin_binding(store, tenant_id=str(tenant_id or ""))
        if isinstance(binding, dict):
            chat_id = str(
                binding.get("external_chat_id") or binding.get("external_user_id") or ""
            ).strip()
            if not account_id or account_id == "weixin-default":
                account_id = str(binding.get("account_id") or account_id or "").strip()
            if channel in {"wechat", "weixin"}:
                channel = normalize_weixin_channel(str(binding.get("channel") or channel))

    context_token = str(wx.get("context_token") or "").strip()
    getter = getattr(store, "get_channel_context_token_fuzzy", None)
    if callable(getter) and chat_id and not context_token:
        context_token = str(
            getter(
                tenant_id=str(tenant_id or ""),
                channel=channel,
                account_id=account_id,
                external_chat_id=chat_id,
            )
            or ""
        ).strip()

    return {
        "channel": channel,
        "chat_id": chat_id,
        "account_id": account_id,
        "context_token": context_token,
    }


__all__ = ["normalize_weixin_channel", "resolve_weixin_delivery_target"]
