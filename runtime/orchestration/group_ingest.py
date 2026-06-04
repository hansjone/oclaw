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
) -> bool:
    if not is_group:
        return True
    mention_set = normalize_jids(list(mentions or []))
    bot = normalize_jid(str(bot_jid or ""))
    if bot and bot in mention_set:
        return True
    # Baileys may omit bot from mentionedJid when user uses display-name @; compare user part.
    if bot and "@" in bot:
        bot_user = bot.split("@", 1)[0]
        for m in mention_set:
            if "@" in m and m.split("@", 1)[0] == bot_user:
                return True
    trigger_list = [str(t) for t in (triggers or []) if str(t)]
    body = str(text or "")
    if trigger_list and any(t in body for t in trigger_list):
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
    sender_jid = normalize_jid(str(getattr(inbound, "external_user_id", "") or ""))
    chat_id = str(getattr(inbound, "external_chat_id", "") or "").strip()
    stanza_id = str(raw.get("id") or meta.get("message_id") or "").strip()
    participant = normalize_jid(str(raw.get("participant") or sender_jid or ""))
    quote_text = str(getattr(inbound, "text", "") or "").strip()
    push_name = str(raw.get("pushName") or meta.get("push_name") or "").strip()
    out: dict[str, Any] = {
        "is_group": True,
        "reply_to_user_id": sender_jid,
        "mention_jids": [sender_jid] if sender_jid else [],
        "quote_remote_jid": chat_id,
        "quote_stanza_id": stanza_id,
        "quote_participant": participant,
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
    "normalize_jid",
    "normalize_jids",
    "infer_is_group_from_chat_id",
    "is_nonsend_channel_reply_text",
    "resolve_is_group",
    "resolve_group_policy",
    "session_user_key",
    "should_process_group_inbound",
    "should_send_channel_reply_text",
]
