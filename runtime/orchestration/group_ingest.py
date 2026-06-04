from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

GROUP_SESSION_USER_SENTINEL = "__group__"


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


__all__ = [
    "GROUP_SESSION_USER_SENTINEL",
    "GroupPolicyConfig",
    "build_group_sender_context",
    "normalize_jid",
    "normalize_jids",
    "resolve_group_policy",
    "session_user_key",
    "should_process_group_inbound",
]
