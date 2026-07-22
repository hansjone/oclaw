from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

GROUP_SESSION_USER_SENTINEL = "__group__"
_NONSEND_REPLY_TEXTS = frozenset(
    {
        "(silent)",
        "[silent]",
        "no_reply",
        "no reply",
        "静默",
    }
)


def normalize_jid(jid: str) -> str:
    s = str(jid or "").strip().lower()
    if not s:
        return ""
    if "@" in s:
        user, domain = s.split("@", 1)
        user = user.split(":")[0]
        return f"{user}@{domain}"
    return s.split(":")[0]


def jid_phone(jid: str) -> str:
    head = str(jid or "").strip().split("@", 1)[0]
    head = head.split(":", 1)[0]
    return re.sub(r"\D", "", head)


def jid_base_local(jid: str) -> str:
    s = str(jid or "").strip().lower()
    if not s:
        return ""
    return s.split("@", 1)[0].split(":", 1)[0]


def jids_same_user(a: str, b: str) -> bool:
    na = normalize_jid(a)
    nb = normalize_jid(b)
    if na and nb and na == nb:
        return True
    la = jid_base_local(a)
    lb = jid_base_local(b)
    if la and lb and la == lb:
        digits = re.sub(r"\D", "", la)
        if len(digits) >= 6:
            return True
    pa = jid_phone(a)
    pb = jid_phone(b)
    return len(pa) >= 6 and pa == pb


def _bot_identity_jids(*, bot_jid: str | None, metadata: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for candidate in [bot_jid]:
        s = str(candidate or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    if isinstance(metadata, dict):
        for key in ("bot_lid", "botLid"):
            s = str(metadata.get(key) or "").strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        raw = _metadata_raw(metadata)
        for key in ("botLid", "bot_lid"):
            s = str(raw.get(key) or "").strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
    return out


def _metadata_raw(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    raw = metadata.get("raw")
    return raw if isinstance(raw, dict) else {}


def metadata_mentions_bot(metadata: dict[str, Any] | None) -> bool:
    """Sidecar hint when WhatsApp omits mentionedJid (display-name @)."""
    if not isinstance(metadata, dict):
        return False
    if metadata.get("mentions_bot") is True or metadata.get("mentionsBot") is True:
        return True
    raw = _metadata_raw(metadata)
    return raw.get("mentionsBot") is True or raw.get("mentions_bot") is True


def mentions_include_bot(
    *,
    mentions: list[str],
    bot_jid: str | None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    identities = _bot_identity_jids(bot_jid=bot_jid, metadata=metadata)
    if not identities:
        return False
    for raw in mentions or []:
        mention = str(raw or "").strip()
        if not mention:
            continue
        for identity in identities:
            if jids_same_user(mention, identity):
                return True
    return False


def text_mentions_bot(*, text: str, bot_jid: str | None) -> bool:
    """Fallback when WhatsApp omits mentionedJid but user visibly @-mentions the bot."""
    bot = str(bot_jid or "").strip()
    if not bot:
        return False
    phone = jid_phone(bot)
    if len(phone) < 6:
        return False
    body = str(text or "")
    if "@" not in body:
        return False
    digits_in_text = re.sub(r"\D", "", body)
    return phone in digits_in_text


def is_reply_to_bot(*, metadata: dict[str, Any] | None, bot_jid: str | None) -> bool:
    raw = _metadata_raw(metadata)
    if raw.get("isReplyToBot") is True or raw.get("is_reply_to_bot") is True:
        return True
    quoted = ""
    if isinstance(metadata, dict):
        quoted = str(metadata.get("quoted_participant") or "").strip()
    if not quoted:
        quoted = str(raw.get("quotedParticipant") or raw.get("quoted_participant") or "").strip()
    bot = str(bot_jid or "").strip()
    if quoted and bot and jids_same_user(quoted, bot):
        return True
    return False


def extract_quoted_ume_alert_text(*, metadata: dict[str, Any] | None) -> str:
    raw = _metadata_raw(metadata)
    quoted_text = str(raw.get("quotedText") or raw.get("quoted_text") or "").strip()
    if quoted_text and (quoted_text.startswith("[UME") or "[UME Alarm" in quoted_text[:120]):
        return quoted_text
    return ""


def extract_group_quoted_message(*, metadata: dict[str, Any] | None) -> dict[str, str]:
    raw = _metadata_raw(metadata)
    quoted_text = str(raw.get("quotedText") or raw.get("quoted_text") or "").strip()
    quoted_participant = str(raw.get("quotedParticipant") or raw.get("quoted_participant") or "").strip()
    push_name = str(raw.get("quotedPushName") or raw.get("quoted_push_name") or "").strip()
    stanza_id = str(raw.get("quotedStanzaId") or raw.get("quoted_stanza_id") or "").strip()
    return {
        "quoted_text": quoted_text,
        "quoted_participant": quoted_participant,
        "quoted_push_name": push_name,
        "quoted_stanza_id": stanza_id,
    }


def _normalize_quoted_compare_text(text: str) -> str:
    """Normalize quote/history text for dedupe.

    WhatsApp reply-to often prefixes the bot body with ``@<lid|phone>``; session
    assistant rows usually do not. Strip those so same-session quotes match.
    """
    s = str(text or "").strip()
    if not s:
        return ""
    # Drop leading @tokens (jid / phone / display-name mentions).
    s = re.sub(r"^(?:@\S+\s+)+", "", s)
    # Drop common group-ingest wrappers if somehow present.
    s = re.sub(r"^\[被引用消息\]\s*", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:400]


def _quoted_texts_overlap(quoted: str, history: str) -> bool:
    """True when quote body is essentially the same as a history row."""
    q = _normalize_quoted_compare_text(quoted)
    h = _normalize_quoted_compare_text(history)
    if not q or not h:
        return False
    if q == h:
        return True
    q_fp = q[:160]
    h_fp = h[:160]
    if q_fp == h_fp:
        return True
    # Substantial containment only — avoid short-string false positives.
    min_len = 48
    if len(q_fp) >= min_len and q_fp in h:
        return True
    if len(h_fp) >= min_len and h_fp in q:
        return True
    if len(q) >= min_len and len(h) >= min_len:
        n = 0
        for a, b in zip(q_fp, h_fp):
            if a != b:
                break
            n += 1
        if n >= min_len:
            return True
    return False


def should_inject_quoted_context(*, quoted_text: str, recent_messages: list[Any]) -> bool:
    """Return False when quoted body already appears in recent session history.

    Prefer assistant rows (same-session bot replies). Also scan other roles as a
    fallback so previously injected ``[被引用消息]`` user rows still dedupe.
    """
    token = _normalize_quoted_compare_text(quoted_text)
    if not token:
        return False

    assistants: list[Any] = []
    others: list[Any] = []
    for row in recent_messages or []:
        role = str(getattr(row, "role", "") or "").strip().lower()
        if role == "assistant":
            assistants.append(row)
        else:
            others.append(row)

    for row in assistants:
        if _quoted_texts_overlap(token, str(getattr(row, "content", "") or "")):
            return False
    for row in others:
        if _quoted_texts_overlap(token, str(getattr(row, "content", "") or "")):
            return False
    return True


def build_group_quoted_context_block(*, metadata: dict[str, Any] | None) -> str:
    info = extract_group_quoted_message(metadata=metadata)
    quoted_text = str(info.get("quoted_text") or "").strip()
    if not quoted_text:
        return ""
    quoted_participant = str(info.get("quoted_participant") or "").strip()
    quoted_push_name = str(info.get("quoted_push_name") or "").strip()
    speaker = quoted_push_name or quoted_participant or "unknown"
    return f"[被引用消息]\n{speaker}: {quoted_text}"


def enrich_alert_group_question(*, user_text: str, quoted_alert: str) -> str:
    body = str(user_text or "").strip()
    quote = str(quoted_alert or "").strip()
    if not quote:
        return body
    if not body:
        return f"[Quoted UME alarm]\n{quote}"
    return f"[Quoted UME alarm]\n{quote}\n\n[User question]\n{body}"


def normalize_jids(jids: list[str]) -> set[str]:
    out: set[str] = set()
    for raw in jids or []:
        n = normalize_jid(raw)
        if n:
            out.add(n)
    return out


def normalize_group_session_scope(raw: Any) -> str:
    scope = str(raw or "").strip().lower()
    if scope in {"chat", "shared", "shared_chat"}:
        return "chat"
    if scope in {"user", "user_in_chat", "per_user", "member"}:
        return "user_in_chat"
    return "user_in_chat"


def session_user_key(*, is_group: bool, external_user_id: str, session_scope: str = "user_in_chat") -> str:
    if not is_group:
        return str(external_user_id or "").strip()
    if normalize_group_session_scope(session_scope) == "chat":
        return GROUP_SESSION_USER_SENTINEL
    return str(external_user_id or "").strip()


def infer_is_group_from_chat_id(chat_id: str) -> bool:
    c = str(chat_id or "").strip().lower()
    return c.endswith("@g.us")


def resolve_is_group(*, payload_is_group: bool, chat_id: str) -> bool:
    if payload_is_group:
        return True
    return infer_is_group_from_chat_id(chat_id)


def is_nonsend_channel_reply_text(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return True
    normalized = t.lower().replace("（", "(").replace("）", ")")
    if normalized in _NONSEND_REPLY_TEXTS:
        return True
    return bool(re.fullmatch(r"no_reply", normalized, flags=re.IGNORECASE))


def should_send_channel_reply_text(text: str) -> bool:
    return not is_nonsend_channel_reply_text(text)


@dataclass(frozen=True)
class GroupPolicyConfig:
    require_mention: bool = True
    triggers: tuple[str, ...] = ("/oclaw",)
    session_scope: str = "user_in_chat"


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


def _parse_triggers_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = str(os.environ.get(name) or "").strip()
    if not raw:
        return default
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return tuple(parts) if parts else default


def _parse_group_policy_dict(raw: Any) -> GroupPolicyConfig | None:
    if not isinstance(raw, dict):
        return None
    require_mention = raw.get("require_mention")
    triggers_raw = raw.get("triggers")
    session_scope = raw.get("session_scope")
    triggers: tuple[str, ...] | None = None
    if isinstance(triggers_raw, list):
        triggers = tuple(str(x).strip() for x in triggers_raw if str(x).strip())
    return GroupPolicyConfig(
        require_mention=bool(require_mention) if require_mention is not None else True,
        triggers=triggers if triggers is not None else ("/oclaw",),
        session_scope=normalize_group_session_scope(session_scope),
    )


def resolve_group_policy(*, account: dict[str, Any] | None = None) -> GroupPolicyConfig:
    cfg = (account or {}).get("config")
    if isinstance(cfg, dict):
        gp = _parse_group_policy_dict(cfg.get("group_policy"))
        if gp is not None:
            return gp
        gp = _parse_group_policy_dict(cfg.get("group"))
        if gp is not None:
            return gp
    return GroupPolicyConfig(
        require_mention=_parse_bool_env("AIA_WHATSAPP_GROUP_REQUIRE_MENTION", True),
        triggers=_parse_triggers_env("AIA_WHATSAPP_GROUP_TRIGGERS", ("/oclaw", "|oclaw")),
        session_scope=normalize_group_session_scope(os.environ.get("AIA_WHATSAPP_GROUP_SESSION_SCOPE")),
    )


def should_process_group_inbound(
    *,
    is_group: bool,
    text: str,
    mentions: list[str],
    bot_jid: str | None,
    require_mention: bool = True,
    triggers: list[str] | tuple[str, ...] | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    if not is_group:
        return True

    mentions_list = [str(m).strip() for m in (mentions or []) if str(m).strip()]
    trigger_list = [str(t) for t in (triggers or []) if str(t)]
    body = str(text or "")
    has_trigger = bool(trigger_list and any(t in body for t in trigger_list))
    bot_mentioned = mentions_include_bot(
        mentions=mentions_list,
        bot_jid=bot_jid,
        metadata=metadata,
    ) or text_mentions_bot(text=text, bot_jid=bot_jid)

    # Multi-@: reply only when the bot is among mentionedJid; @ others alone stays silent.
    if mentions_list:
        if bot_mentioned:
            return True
        return has_trigger

    if metadata_mentions_bot(metadata):
        return True
    if is_reply_to_bot(metadata=metadata, bot_jid=bot_jid):
        return True
    if has_trigger:
        return True
    return not require_mention


def build_group_sender_context(*, metadata: dict[str, Any] | None, external_user_id: str) -> str:
    meta = metadata if isinstance(metadata, dict) else {}
    raw = meta.get("raw") if isinstance(meta.get("raw"), dict) else {}
    push_name = str(raw.get("pushName") or meta.get("push_name") or meta.get("display_name") or "").strip()
    sender = str(external_user_id or "").strip()
    label = push_name or sender or "unknown"
    return f"[发言: {label}]"


def _mention_tokens_for_jids(jids: list[str]) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for jid in jids or []:
        local = jid_base_local(jid)
        if local:
            tok = f"@{local}"
            if tok.lower() not in seen:
                seen.add(tok.lower())
                tokens.append(tok)
        phone = jid_phone(jid)
        if phone and len(phone) >= 6:
            tok = f"@{phone}"
            if tok.lower() not in seen:
                seen.add(tok.lower())
                tokens.append(tok)
    return tokens


def strip_bot_mentions_from_text(
    *,
    text: str,
    bot_jid: str | None,
    metadata: dict[str, Any] | None = None,
) -> str:
    body = str(text or "")
    identities = _bot_identity_jids(bot_jid=bot_jid, metadata=metadata)
    tokens = _mention_tokens_for_jids(identities)
    extra_names: set[str] = set()
    if isinstance(metadata, dict):
        for name in (metadata.get("bot_push_name"), "oliver"):
            n = str(name or "").strip()
            if n:
                extra_names.add(n.lower())
    for token in sorted(tokens, key=len, reverse=True):
        body = re.sub(
            re.escape(token) + r"(?=\s|$|[，。！？!?,.])",
            "",
            body,
            flags=re.IGNORECASE,
        )
    for name in sorted(extra_names, key=len, reverse=True):
        body = re.sub(
            rf"@{re.escape(name)}(?=\s|$|[，。！？!?,.])",
            "",
            body,
            flags=re.IGNORECASE,
        )
    body = re.sub(r"\s{2,}", " ", body).strip()
    return body


def _filter_non_bot_mention_jids(
    mention_jids: list[str],
    *,
    bot_jid: str | None,
    metadata: dict[str, Any] | None = None,
) -> list[str]:
    identities = _bot_identity_jids(bot_jid=bot_jid, metadata=metadata)
    out: list[str] = []
    seen: set[str] = set()
    for raw in mention_jids or []:
        jid = str(raw or "").strip()
        if not jid:
            continue
        if any(jids_same_user(jid, identity) for identity in identities):
            continue
        key = jid_base_local(jid) or jid.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(jid)
    return out


def normalize_mentioned_users_in_text(
    *,
    text: str,
    mention_jids: list[str],
    mention_names: list[str] | None = None,
    store: Any = None,
    tenant_id: str = "",
    account_id: str = "",
) -> str:
    body = str(text or "")
    names = [str(x or "").strip() for x in (mention_names or [])]
    for idx, jid in enumerate(mention_jids or []):
        jid_s = str(jid or "").strip()
        if not jid_s:
            continue
        name = names[idx] if idx < len(names) and names[idx] else ""
        if not name and store is not None:
            from runtime.scheduler.whatsapp_mentions import _lookup_push_name

            name = _lookup_push_name(
                store,
                tenant_id=str(tenant_id or ""),
                account_id=str(account_id or ""),
                jid=jid_s,
            )
        if not name:
            local = jid_base_local(jid_s)
            if local:
                body = re.sub(
                    rf"@{re.escape(local)}(?=\s|$|[，。！？!?,.])",
                    "",
                    body,
                )
            continue
        local = jid_base_local(jid_s)
        if local:
            body = re.sub(
                rf"@{re.escape(local)}(?=\s|$|[，。！？!?,.])",
                f"@{name}",
                body,
            )
        phone = jid_phone(jid_s)
        if phone and len(phone) >= 6:
            body = re.sub(
                rf"@{re.escape(phone)}(?=\s|$|[，。！？!?,.])",
                f"@{name}",
                body,
            )
    body = re.sub(r"\s{2,}", " ", body).strip()
    return body


def prepare_group_user_text_for_model(
    *,
    text: str,
    metadata: dict[str, Any] | None,
    mentions: list[str],
    bot_jid: str | None,
    session_scope: str,
    external_user_id: str,
    filtered_mention_jids: list[str] | None = None,
    mention_names: list[str] | None = None,
    store: Any = None,
    tenant_id: str = "",
    account_id: str = "",
    quoted_ctx: str = "",
) -> str:
    body = str(text or "").strip()
    body = strip_bot_mentions_from_text(text=body, bot_jid=bot_jid, metadata=metadata)
    target_jids = (
        filtered_mention_jids
        if filtered_mention_jids is not None
        else _filter_non_bot_mention_jids(list(mentions or []), bot_jid=bot_jid, metadata=metadata)
    )
    body = normalize_mentioned_users_in_text(
        text=body,
        mention_jids=target_jids,
        mention_names=mention_names,
        store=store,
        tenant_id=tenant_id,
        account_id=account_id,
    )
    prefix_parts: list[str] = []
    if normalize_group_session_scope(session_scope) == "chat":
        prefix_parts.append(
            build_group_sender_context(metadata=metadata, external_user_id=external_user_id)
        )
    quote = str(quoted_ctx or "").strip()
    if quote:
        prefix_parts.append(quote)
    prefix = "\n".join(part for part in prefix_parts if str(part).strip())
    if prefix and body:
        return f"{prefix}\n{body}"
    return prefix or body


def build_group_focus_instruction(*, lang: str = "zh") -> str:
    if str(lang or "").strip().lower().startswith("en"):
        return (
            "[Group chat rule: answer only the current sender's request. "
            "Do not assume context from other members unless this message explicitly quotes or references it.]"
        )
    return "[群聊规则：只回答当前发言人的问题；除非本条消息明确引用或承接前文，否则不要默认继承其他群成员的上下文。]"


def build_channel_file_delivery_instruction(*, lang: str = "zh") -> str:
    if str(lang or "").strip().lower().startswith("en"):
        return (
            "[Channel rule: to send any generated attachment back to the user on WhatsApp/WeChat "
            "(documents, images, videos), call save_deliverable_attachment with path or attachment_id. "
            "write_file, run_command, and image generation alone do not attach files to the outbound message.]"
        )
    return (
        "[渠道规则：若要把生成的附件发回用户（WhatsApp/微信，含文档/图片/视频），"
        "必须调用 save_deliverable_attachment（path 或 attachment_id）；"
        "write_file、run_command、生图工具 alone 不会随消息发送附件。]"
    )


def build_whatsapp_group_reply_metadata(
    *,
    inbound: Any,
) -> dict[str, Any]:
    """Outbound hints for WhatsApp sidecar: @ sender + quote original message."""
    meta = inbound.metadata if isinstance(getattr(inbound, "metadata", None), dict) else {}
    raw = meta.get("raw") if isinstance(meta.get("raw"), dict) else {}
    sender_jid = str(getattr(inbound, "external_user_id", "") or "").strip()
    chat_id = str(getattr(inbound, "external_chat_id", "") or "").strip()
    participant_raw = str(raw.get("participant") or sender_jid or "").strip()
    stanza_id = str(raw.get("id") or meta.get("message_id") or "").strip()
    quote_text = str(getattr(inbound, "text", "") or "").strip()
    push_name = str(raw.get("pushName") or meta.get("push_name") or "").strip()
    out: dict[str, Any] = {
        "is_group": True,
        "reply_to_user_id": participant_raw or normalize_jid(sender_jid),
        "mention_jids": [participant_raw] if participant_raw else ([normalize_jid(sender_jid)] if sender_jid else []),
        "quote_remote_jid": chat_id,
        "quote_stanza_id": stanza_id,
        "quote_participant": participant_raw or normalize_jid(str(raw.get("participant") or sender_jid or "")),
        "quote_text": quote_text,
    }
    if push_name:
        out["quote_push_name"] = push_name
        out["mention_names"] = [push_name]
    return out


__all__ = [
    "GROUP_SESSION_USER_SENTINEL",
    "GroupPolicyConfig",
    "build_channel_file_delivery_instruction",
    "build_group_sender_context",
    "build_group_focus_instruction",
    "build_group_quoted_context_block",
    "build_whatsapp_group_reply_metadata",
    "enrich_alert_group_question",
    "extract_group_quoted_message",
    "extract_quoted_ume_alert_text",
    "mentions_include_bot",
    "metadata_mentions_bot",
    "normalize_mentioned_users_in_text",
    "normalize_jid",
    "normalize_group_session_scope",
    "normalize_jids",
    "prepare_group_user_text_for_model",
    "strip_bot_mentions_from_text",
    "infer_is_group_from_chat_id",
    "is_nonsend_channel_reply_text",
    "resolve_is_group",
    "resolve_group_policy",
    "session_user_key",
    "should_inject_quoted_context",
    "should_process_group_inbound",
    "should_send_channel_reply_text",
    "text_mentions_bot",
]
