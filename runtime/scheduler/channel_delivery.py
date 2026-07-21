from __future__ import annotations

import json
import os
from typing import Any

from runtime.orchestration.group_ingest import is_nonsend_channel_reply_text
from runtime.scheduler.session_resolver import parse_delivery_json
from runtime.scheduler.whatsapp_mentions import (
    encode_whatsapp_outbound_source,
    format_whatsapp_mention_text,
    infer_whatsapp_mention_jids_from_text,
    normalize_whatsapp_mention_jids,
)


def _encode_weixin_outbound_source(
    *,
    context_token: str,
    attachments: list[dict[str, Any]] | None = None,
    media_path: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "kind": "scheduled_job",
        "context_token": str(context_token or "").strip(),
    }
    atts = [a for a in (attachments or []) if isinstance(a, dict)]
    if atts:
        payload["attachments"] = atts
    mp = str(media_path or "").strip()
    if mp:
        payload["media_path"] = mp
    return json.dumps(payload, ensure_ascii=False)


def _decode_weixin_outbound_source(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def enqueue_weixin_reply(
    *,
    channel: str,
    account_id: str,
    chat_id: str,
    text: str,
    context_token: str = "",
    store: Any = None,
    tenant_id: str = "",
    attachments: list[dict[str, Any]] | None = None,
    media_path: str | None = None,
) -> dict[str, Any]:
    from runtime.scheduler.weixin_delivery import normalize_weixin_channel

    ctx_tok = str(context_token or "").strip()
    if not ctx_tok:
        return {
            "ok": False,
            "channel": normalize_weixin_channel(channel),
            "error": "context_token_missing",
            "hint": "Send any message to the bot on WeChat first, then retry the scheduled job.",
        }
    durable_id = ""
    enqueuer = getattr(store, "enqueue_channel_outbound_message", None)
    if store is not None and callable(enqueuer):
        try:
            durable_id = str(
                enqueuer(
                    channel=normalize_weixin_channel(channel),
                    chat_id=str(chat_id or "").strip(),
                    text=str(text or ""),
                    tenant_id=str(tenant_id or ""),
                    account_id=str(account_id or "").strip(),
                    source=_encode_weixin_outbound_source(
                        context_token=ctx_tok,
                        attachments=attachments,
                        media_path=media_path,
                    ),
                )
                or ""
            ).strip()
        except Exception:
            durable_id = ""
    try:
        from interfaces.http.weixin_ilink_api import enqueue_weixin_outbound_reply
    except Exception as exc:
        if durable_id:
            return {
                "ok": True,
                "channel": normalize_weixin_channel(channel),
                "message_id": durable_id,
                "queued": True,
                "durable": True,
                "context_token_present": True,
                "bridge_error": f"{type(exc).__name__}: {exc}",
            }
        return {"ok": False, "channel": channel, "error": f"{type(exc).__name__}: {exc}"}
    try:
        bridge_seq = enqueue_weixin_outbound_reply(
            channel=normalize_weixin_channel(channel),
            account_id=str(account_id or "").strip(),
            chat_id=str(chat_id or "").strip(),
            text=text,
            context_token=ctx_tok,
            attachments=attachments,
            media_path=media_path,
        )
        return {
            "ok": True,
            "channel": normalize_weixin_channel(channel),
            "message_id": durable_id or bridge_seq,
            "bridge_seq": bridge_seq,
            "queued": True,
            "durable": bool(durable_id),
            "context_token_present": True,
            "account_id": str(account_id or "").strip(),
            "chat_id": str(chat_id or "").strip(),
        }
    except Exception as exc:
        if durable_id:
            return {
                "ok": True,
                "channel": normalize_weixin_channel(channel),
                "message_id": durable_id,
                "queued": True,
                "durable": True,
                "context_token_present": True,
                "bridge_error": f"{type(exc).__name__}: {exc}",
            }
        return {"ok": False, "channel": channel, "error": f"{type(exc).__name__}: {exc}"}


def persist_channel_context_token(
    store: Any,
    *,
    tenant_id: str,
    channel: str,
    account_id: str,
    external_chat_id: str,
    context_token: str,
) -> None:
    from runtime.scheduler.weixin_delivery import normalize_weixin_channel

    setter = getattr(store, "set_channel_context_token", None)
    if not callable(setter):
        return
    tok = str(context_token or "").strip()
    chat_id = str(external_chat_id or "").strip()
    if not tok or not chat_id:
        return
    tid = str(tenant_id or "")
    acct = str(account_id or "").strip()
    channels = []
    for ch in (channel, "wechat", "weixin"):
        c = normalize_weixin_channel(str(ch or "")) if str(ch or "").lower() in {"wechat", "weixin"} else str(ch or "").strip().lower()
        if c and c not in channels:
            channels.append(c)
    account_ids = [acct] if acct else [""]
    if acct:
        account_ids.append("")
    for ch in channels:
        for aid in account_ids:
            setter(
                tenant_id=tid,
                channel=ch,
                account_id=aid,
                external_chat_id=chat_id,
                context_token=tok,
            )


def _collect_scheduled_turn_attachments(
    *,
    store: Any,
    session_id: str,
    turn_uuid: str,
) -> list[dict[str, Any]]:
    from runtime.application.gateway.inbound_service import (
        _is_channel_deliverable_attachment,
        _parse_message_attachments,
    )

    sid = str(session_id or "").strip()
    tu = str(turn_uuid or "").strip()
    if not sid:
        return []
    try:
        rows = store.get_messages(session_id=sid, limit=120)
    except Exception:
        rows = []
    deliverable: list[dict[str, Any]] = []
    for row in reversed(list(rows or [])):
        role = str(getattr(row, "role", "") or "").strip().lower()
        if role != "tool":
            continue
        if tu and str(getattr(row, "turn_uuid", "") or "").strip() != tu:
            continue
        for att in _parse_message_attachments(getattr(row, "attachments", None)):
            if _is_channel_deliverable_attachment(att):
                deliverable.append(att)
    return deliverable


def _prepare_channel_outbound_attachments(
    attachments: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    if not attachments:
        return [], ""
    reply: dict[str, Any] = {"attachments": list(attachments)}
    from runtime.application.gateway.inbound_service import (
        _maybe_add_media_path_for_wechat_reply,
        _maybe_expand_reply_attachments_for_channel,
    )

    _maybe_expand_reply_attachments_for_channel(reply)
    _maybe_add_media_path_for_wechat_reply(reply)
    out_atts = [a for a in (reply.get("attachments") or []) if isinstance(a, dict)]
    return out_atts, str(reply.get("media_path") or "").strip()


def extract_context_token_from_inbound_metadata(metadata: dict[str, Any] | None) -> str:
    meta = metadata if isinstance(metadata, dict) else {}
    raw = meta.get("raw") if isinstance(meta.get("raw"), dict) else {}
    msg = raw.get("msg") if isinstance(raw.get("msg"), dict) else {}
    for candidate in (
        msg.get("context_token"),
        (raw.get("metadata") or {}).get("context_token") if isinstance(raw.get("metadata"), dict) else None,
        raw.get("context_token"),
        meta.get("context_token"),
    ):
        tok = str(candidate or "").strip()
        if tok:
            return tok
    return ""


def deliver_scheduled_reply(
    store: Any,
    *,
    tenant_id: str,
    reply_text: str,
    delivery_json: str,
    resolved_channel: str = "",
    resolved_chat_id: str = "",
    resolved_account_id: str = "",
    session_id: str = "",
    turn_uuid: str = "",
) -> dict[str, Any]:
    text = str(reply_text or "").strip()
    if is_nonsend_channel_reply_text(text):
        text = ""
    outbound_attachments, media_path = _prepare_channel_outbound_attachments(
        _collect_scheduled_turn_attachments(
            store=store,
            session_id=session_id,
            turn_uuid=turn_uuid,
        )
    )
    has_attachments = bool(outbound_attachments or media_path)
    if not text and not has_attachments:
        return {"ok": False, "skipped": True, "reason": "empty_or_silent_reply"}

    ch_lower = str(resolved_channel or "").strip().lower()
    if ch_lower in {"wechat", "weixin"}:
        from runtime.application.gateway.inbound_service import _user_facing_wechat_reply

        text = _user_facing_wechat_reply(reply=text)

    delivery = parse_delivery_json(delivery_json)
    results: dict[str, Any] = {}

    wa = delivery.get("whatsapp") if isinstance(delivery.get("whatsapp"), dict) else {}
    wa_enabled = bool(wa.get("enabled")) and str(wa.get("target_type") or "none") != "none"
    chat_id = str(wa.get("chat_id") or resolved_chat_id or "").strip()
    account_id = str(
        wa.get("account_id") or resolved_account_id or os.getenv("AIA_WHATSAPP_ACCOUNT_ID") or "wa-default"
    ).strip()
    if wa_enabled and chat_id and (text or has_attachments):
        mention_jids = normalize_whatsapp_mention_jids(wa.get("mention_jids"))
        if not mention_jids:
            mention_jids = infer_whatsapp_mention_jids_from_text(
                text,
                store=store,
                tenant_id=tenant_id,
                account_id=account_id,
            )
        mention_names = wa.get("mention_names") if isinstance(wa.get("mention_names"), list) else None
        if mention_names is None and mention_jids:
            from runtime.scheduler.whatsapp_mentions import _lookup_push_name

            derived_names: list[str] = []
            for jid in mention_jids:
                derived_names.append(
                    _lookup_push_name(
                        store,
                        tenant_id=tenant_id,
                        account_id=account_id,
                        jid=str(jid or ""),
                    )
                )
            if any(derived_names):
                mention_names = derived_names
        out_text = format_whatsapp_mention_text(
            text,
            mention_jids,
            store=store,
            tenant_id=tenant_id,
            account_id=account_id,
            mention_names=mention_names,
        )
        msg_id = store.enqueue_channel_outbound_message(
            channel="whatsapp",
            chat_id=chat_id,
            text=out_text,
            tenant_id=tenant_id,
            account_id=account_id,
            source=encode_whatsapp_outbound_source(
                mention_jids=mention_jids,
                mention_names=mention_names,
                mention_text_ready=bool(mention_jids),
                attachments=outbound_attachments if has_attachments else None,
                media_path=media_path or None,
            ),
        )
        results["whatsapp"] = {
            "ok": True,
            "message_id": msg_id,
            "chat_id": chat_id,
            "mention_jids": mention_jids,
            "attachments": len(outbound_attachments) if has_attachments else 0,
        }

    wx = delivery.get("weixin") if isinstance(delivery.get("weixin"), dict) else {}
    wx_enabled = bool(wx.get("enabled", True))
    if wx_enabled and (text or has_attachments):
        from runtime.scheduler.weixin_delivery import resolve_weixin_delivery_target

        target = resolve_weixin_delivery_target(
            store,
            tenant_id=tenant_id,
            session_id=session_id,
            delivery=delivery,
            resolved_channel=resolved_channel,
            resolved_chat_id=resolved_chat_id,
            resolved_account_id=resolved_account_id,
        )
        wx_chat = str(target.get("chat_id") or "").strip()
        wx_account = str(target.get("account_id") or "").strip()
        wx_channel = str(target.get("channel") or "wechat")
        context_token = str(target.get("context_token") or "").strip()
        if wx_chat:
            results["weixin"] = enqueue_weixin_reply(
                channel=wx_channel,
                account_id=wx_account,
                chat_id=wx_chat,
                text=text,
                context_token=context_token,
                store=store,
                tenant_id=tenant_id,
                attachments=outbound_attachments if has_attachments else None,
                media_path=media_path or None,
            )
        else:
            results["weixin"] = {"ok": False, "error": "weixin_chat_missing"}

    if not results:
        return {"ok": True, "skipped": True, "reason": "no_delivery_targets"}

    ok = all(bool((v or {}).get("ok")) for v in results.values() if isinstance(v, dict))
    return {"ok": ok, "channels": results}


__all__ = [
    "deliver_scheduled_reply",
    "enqueue_weixin_reply",
    "extract_context_token_from_inbound_metadata",
    "persist_channel_context_token",
]
