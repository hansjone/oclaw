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


def normalize_jids(jids: list[str]) -> set[str]:
    out: set[str] = set()
    for raw in jids or []:
        n = normalize_jid(raw)
        if n:
            out.add(n)
    return out


def session_user_key(*, is_group: bool, external_user_id: str) -> str:
    return GROUP_SESSION_USER_SENTINEL if is_group else str(external_user_id or "").strip()


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
    session_scope: str = "chat"


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
        session_scope=str(session_scope or "chat").strip() or "chat",
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
    if sender and push_name and sender not in push_name:
        return f"[群成员: {label} ({sender})]"
    return f"[群成员: {label}]"


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
    return out


__all__ = [
    "GROUP_SESSION_USER_SENTINEL",
    "GroupPolicyConfig",
    "build_group_sender_context",
    "build_whatsapp_group_reply_metadata",
    "mentions_include_bot",
    "metadata_mentions_bot",
    "normalize_jid",
    "normalize_jids",
    "infer_is_group_from_chat_id",
    "is_nonsend_channel_reply_text",
    "resolve_is_group",
    "resolve_group_policy",
    "session_user_key",
    "should_process_group_inbound",
    "should_send_channel_reply_text",
    "text_mentions_bot",
]
