from __future__ import annotations

import json
import uuid
from typing import Any

from runtime.extensions.whatsapp.access_control import (
    admin_approval_result_text,
    admin_notify_text,
    default_access_lang,
    default_access_mode,
    denied_reply_text,
    extract_participant_alt,
    extract_push_name,
    extract_quote_context,
    extract_remote_jid_alt,
    is_access_allowed,
    normalize_whatsapp_phone,
    parse_admin_access_command,
    parse_admin_approval_intent,
    parse_pending_id_from_notify_text,
    phone_from_jid,
    resolve_sender_phone,
    resolve_whatsapp_sender_jid,
    whatsapp_sender_lookup_jids,
)
from runtime.extensions.whatsapp.api import is_whatsapp_user_target
from runtime.extensions.whatsapp.tenant import resolve_whatsapp_tenant_id


def _extract_contact_fields(inbound: Any) -> tuple[str, str, str, str]:
    meta = inbound.metadata if isinstance(inbound.metadata, dict) else {}
    push_name = extract_push_name(meta)
    raw_jid = str(inbound.external_user_id or "").strip()
    participant_alt = extract_participant_alt(meta)
    remote_jid_alt = extract_remote_jid_alt(meta)
    canonical_jid = resolve_whatsapp_sender_jid(raw_jid, meta)
    phone = resolve_sender_phone(raw_jid, participant_alt, remote_jid_alt)
    return push_name, phone, raw_jid, canonical_jid


def _link_identity_aliases(
    store: Any,
    *,
    tenant_id: str,
    account_id: str,
    user_id: str,
    jids: tuple[str, ...],
) -> None:
    for jid in jids:
        val = str(jid or "").strip()
        if not val:
            continue
        store.upsert_channel_identity_v2(
            tenant_id=tenant_id,
            channel="whatsapp",
            account_id=account_id,
            external_user_id=val,
            user_id=user_id,
        )


def _ensure_admin_identity(
    store: Any,
    *,
    tenant_id: str,
    account_id: str,
    external_user_id: str,
    participant_alt: str,
    push_name: str,
    phone: str,
) -> dict[str, Any] | None:
    lookup_jids = whatsapp_sender_lookup_jids(external_user_id, participant_alt)
    for jid in lookup_jids:
        ident = store.resolve_user_by_channel_identity_v2(
            channel="whatsapp",
            account_id=account_id,
            external_user_id=jid,
        )
        if ident:
            _link_identity_aliases(
                store,
                tenant_id=tenant_id,
                account_id=account_id,
                user_id=str(ident.get("user_id") or ""),
                jids=lookup_jids,
            )
            return ident

    admin_user = store.get_user_by_username(tenant_id=tenant_id, username="administrator")
    user_id = str((admin_user or {}).get("id") or "")
    if not user_id:
        return _ensure_guest_identity(
            store,
            tenant_id=tenant_id,
            account_id=account_id,
            external_user_id=external_user_id,
            participant_alt=participant_alt,
            push_name=push_name,
            phone=phone,
        )
    _link_identity_aliases(
        store,
        tenant_id=tenant_id,
        account_id=account_id,
        user_id=user_id,
        jids=lookup_jids,
    )
    return store.resolve_user_by_channel_identity_v2(
        channel="whatsapp",
        account_id=account_id,
        external_user_id=lookup_jids[0] if lookup_jids else external_user_id,
    )


def _ensure_guest_identity(
    store: Any,
    *,
    tenant_id: str,
    account_id: str,
    external_user_id: str,
    participant_alt: str,
    push_name: str,
    phone: str,
) -> dict[str, Any] | None:
    lookup_jids = whatsapp_sender_lookup_jids(external_user_id, participant_alt)
    for jid in lookup_jids:
        ident = store.resolve_user_by_channel_identity_v2(
            channel="whatsapp",
            account_id=account_id,
            external_user_id=jid,
        )
        if ident:
            _link_identity_aliases(
                store,
                tenant_id=tenant_id,
                account_id=account_id,
                user_id=str(ident.get("user_id") or ""),
                jids=lookup_jids,
            )
            return ident

    label = str(push_name or "").strip() or phone or external_user_id
    username = f"wa_{phone or uuid.uuid4().hex[:10]}"
    user = store.create_user_account(
        tenant_id=tenant_id,
        username=username,
        display_name=label,
        role="guest",
        password_hash="",
        is_active=True,
    )
    user_id = str((user or {}).get("id") or "")
    if not user_id:
        return None
    _link_identity_aliases(
        store,
        tenant_id=tenant_id,
        account_id=account_id,
        user_id=user_id,
        jids=lookup_jids,
    )
    return store.resolve_user_by_channel_identity_v2(
        channel="whatsapp",
        account_id=account_id,
        external_user_id=lookup_jids[0] if lookup_jids else external_user_id,
    )


def _notify_admins(
    store: Any,
    *,
    tenant_id: str,
    account_id: str,
    lang: str,
    push_name: str,
    external_user_id: str,
    request_text: str,
    pending_id: str,
) -> None:
    admins = store.list_whatsapp_contacts(
        tenant_id=tenant_id,
        account_id=account_id,
        list_type="admin",
    )
    text = admin_notify_text(
        lang=lang,
        push_name=push_name,
        external_user_id=external_user_id,
        request_text=request_text,
        pending_id=pending_id,
    )
    for admin in admins:
        chat_id = str(admin.get("external_user_id") or "").strip()
        if not chat_id or not is_whatsapp_user_target(chat_id):
            continue
        store.enqueue_channel_outbound_message(
            channel="whatsapp",
            chat_id=chat_id,
            text=text,
            tenant_id=tenant_id,
            account_id=account_id,
            source=json.dumps(
                {
                    "kind": "whatsapp_access_pending",
                    "pending_id": str(pending_id or ""),
                },
                ensure_ascii=False,
            ),
        )


def _upsert_whatsapp_contact_profile(
    store: Any,
    *,
    tenant_id: str,
    account_id: str,
    raw_jid: str,
    canonical_jid: str,
    push_name: str,
    phone: str,
) -> None:
    store.upsert_whatsapp_contact(
        tenant_id=tenant_id,
        account_id=account_id,
        external_user_id=raw_jid,
        push_name=push_name,
        phone=phone,
    )
    if canonical_jid and canonical_jid != raw_jid:
        store.upsert_whatsapp_contact(
            tenant_id=tenant_id,
            account_id=account_id,
            external_user_id=canonical_jid,
            push_name=push_name,
            phone=phone_from_jid(canonical_jid),
        )


def _handle_admin_message(
    store: Any,
    *,
    tenant_id: str,
    account_id: str,
    external_user_id: str,
    text: str,
    lang: str,
    inbound: Any,
) -> dict[str, Any] | None:
    cmd = parse_admin_access_command(text)
    if cmd:
        action = str(cmd.get("action") or "")
        if action == "set_mode":
            mode = str(cmd.get("access_mode") or default_access_mode())
            store.upsert_whatsapp_access_config(
                tenant_id=tenant_id,
                account_id=account_id,
                access_mode=mode,
                lang=lang,
            )
            return {"text": f"Access mode set to {mode}.", "metadata": {}}
        if action == "set_list":
            list_type = str(cmd.get("list_type") or "")
            target_raw = str(cmd.get("target") or "").strip()
            try:
                target_phone = normalize_whatsapp_phone(target_raw)
            except Exception:
                return {"text": f"Invalid target: {target_raw}", "metadata": {}}
            store.apply_whatsapp_contact_access(
                tenant_id=tenant_id,
                account_id=account_id,
                external_user_id=target_phone,
                phone=target_phone,
                list_type=list_type,
            )
            return {"text": f"Set {target_phone} as {list_type}.", "metadata": {}}

    meta = inbound.metadata if isinstance(inbound.metadata, dict) else {}
    quote = extract_quote_context(meta)
    stanza_id = str(quote.get("stanza_id") or "").strip()
    quoted_text = str(quote.get("quoted_text") or "").strip()
    if not stanza_id and not quoted_text:
        return None

    admin_chat_id = str(getattr(inbound, "external_chat_id", None) or external_user_id or "").strip()
    pending_id = ""
    if stanza_id:
        found = store.find_whatsapp_pending_by_notify_stanza(
            tenant_id=tenant_id,
            account_id=account_id,
            admin_chat_id=admin_chat_id,
            notify_stanza_id=stanza_id,
        )
        if found:
            pending_id = str(found)

    if not pending_id and quoted_text:
        fallback = parse_pending_id_from_notify_text(quoted_text)
        if fallback:
            pending_id = fallback

    if not pending_id:
        return None

    item = store.get_whatsapp_access_pending_by_id(pending_id=pending_id)
    if not item or str(item.get("status") or "").strip().lower() != "pending":
        return None

    intent = parse_admin_approval_intent(text)
    if not intent:
        return None

    target_jid = str(item.get("external_user_id") or "").strip()
    target_name = str(item.get("push_name") or "").strip()
    target_phone = str(item.get("phone") or "").strip() or resolve_sender_phone(target_jid)
    approved = intent == "approve"
    if approved:
        store.apply_whatsapp_contact_access(
            tenant_id=tenant_id,
            account_id=account_id,
            external_user_id=target_phone,
            push_name=target_name,
            phone=target_phone,
            list_type="whitelist",
        )
        store.resolve_whatsapp_access_pending(
            pending_id=pending_id,
            status="approved",
            resolved_by=external_user_id,
        )
    else:
        if target_phone:
            store.apply_whatsapp_contact_access(
                tenant_id=tenant_id,
                account_id=account_id,
                external_user_id=target_phone,
                push_name=target_name,
                phone=target_phone,
                list_type="blacklist",
            )
        store.resolve_whatsapp_access_pending(
            pending_id=pending_id,
            status="denied",
            resolved_by=external_user_id,
        )
    deleter = getattr(store, "delete_whatsapp_pending_notify_for_pending", None)
    if callable(deleter):
        deleter(pending_id=pending_id)

    raw = meta.get("raw") if isinstance(meta.get("raw"), dict) else {}
    reply_meta: dict[str, Any] = {
        "quote_remote_jid": admin_chat_id,
        "quote_stanza_id": str(raw.get("id") or "").strip(),
        "quote_participant": str(raw.get("participant") or external_user_id or "").strip(),
        "quote_text": str(text or "").strip(),
    }
    return {
        "text": admin_approval_result_text(
            lang=lang,
            approved=approved,
            push_name=target_name,
            external_user_id=target_jid,
        ),
        "metadata": reply_meta,
    }


def handle_whatsapp_access(
    store: Any,
    *,
    inbound: Any,
    account_id: str,
    text: str,
) -> dict[str, Any] | None:
    """Return an inbound response dict when access gate short-circuits normal processing."""
    tenant_id = resolve_whatsapp_tenant_id(store, account_id=account_id)
    meta = inbound.metadata if isinstance(inbound.metadata, dict) else {}
    participant_alt = extract_participant_alt(meta)
    remote_jid_alt = extract_remote_jid_alt(meta)
    push_name, phone, raw_jid, canonical_jid = _extract_contact_fields(inbound)
    if not raw_jid:
        return None

    cfg = store.get_whatsapp_access_config(tenant_id=tenant_id, account_id=account_id)
    access_mode = str((cfg or {}).get("access_mode") or default_access_mode())
    lang = str((cfg or {}).get("lang") or default_access_lang())

    matched = store.find_whatsapp_contact_for_sender(
        tenant_id=tenant_id,
        account_id=account_id,
        external_user_id=raw_jid,
        participant_alt=participant_alt,
        remote_jid_alt=remote_jid_alt,
    )
    list_type = str((matched or {}).get("list_type") or "").strip().lower() or None

    if list_type == "admin":
        admin_reply = _handle_admin_message(
            store,
            tenant_id=tenant_id,
            account_id=account_id,
            external_user_id=raw_jid,
            text=text,
            lang=lang,
            inbound=inbound,
        )
        if admin_reply:
            return {
                "ok": True,
                "replies": [
                    {
                        "channel": "whatsapp",
                        "chat_id": inbound.external_chat_id,
                        "text": str(admin_reply.get("text") or ""),
                        "attachments": [],
                        "metadata": admin_reply.get("metadata")
                        if isinstance(admin_reply.get("metadata"), dict)
                        else {},
                    }
                ],
                "whatsapp_access": "admin_command",
            }
        _upsert_whatsapp_contact_profile(
            store,
            tenant_id=tenant_id,
            account_id=account_id,
            raw_jid=raw_jid,
            canonical_jid=canonical_jid,
            push_name=push_name,
            phone=phone,
        )
        _ensure_admin_identity(
            store,
            tenant_id=tenant_id,
            account_id=account_id,
            external_user_id=raw_jid,
            participant_alt=participant_alt,
            push_name=push_name,
            phone=phone,
        )
        return None

    if is_access_allowed(access_mode=access_mode, list_type=list_type):
        _upsert_whatsapp_contact_profile(
            store,
            tenant_id=tenant_id,
            account_id=account_id,
            raw_jid=raw_jid,
            canonical_jid=canonical_jid,
            push_name=push_name,
            phone=phone,
        )
        _ensure_guest_identity(
            store,
            tenant_id=tenant_id,
            account_id=account_id,
            external_user_id=raw_jid,
            participant_alt=participant_alt,
            push_name=push_name,
            phone=phone,
        )
        return None

    pending_id = store.create_whatsapp_access_pending(
        tenant_id=tenant_id,
        account_id=account_id,
        external_user_id=raw_jid,
        push_name=push_name,
        phone=phone,
        request_text=text,
    )
    if pending_id:
        _notify_admins(
            store,
            tenant_id=tenant_id,
            account_id=account_id,
            lang=lang,
            push_name=push_name,
            external_user_id=raw_jid,
            request_text=text,
            pending_id=pending_id,
        )

    reply_meta: dict[str, Any] = {}
    if bool(getattr(inbound, "is_group", False)):
        raw = meta.get("raw") if isinstance(meta.get("raw"), dict) else {}
        stanza_id = str(raw.get("id") or "").strip()
        quote_participant = str(raw.get("participant") or raw_jid or "").strip()
        reply_meta = {
            "mention_jids": [raw_jid],
            "quote_remote_jid": str(inbound.external_chat_id or "").strip(),
            "quote_stanza_id": stanza_id,
            "quote_participant": quote_participant,
            "quote_text": str(text or "").strip(),
        }

    return {
        "ok": True,
        "replies": [
            {
                "channel": "whatsapp",
                "chat_id": inbound.external_chat_id,
                "text": denied_reply_text(lang=lang),
                "attachments": [],
                "metadata": reply_meta,
            }
        ],
        "whatsapp_access": "denied",
    }


__all__ = ["handle_whatsapp_access"]
