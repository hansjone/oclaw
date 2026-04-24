from __future__ import annotations

import re
from dataclasses import dataclass


TELEGRAM_NUMERIC_CHAT_ID_RE = re.compile(r"^-?\d+$")
TELEGRAM_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,}$")


@dataclass(frozen=True)
class TelegramTarget:
    chat_id: str
    message_thread_id: int | None = None
    chat_type: str = "unknown"  # direct | group | unknown


def strip_telegram_internal_prefixes(value: str) -> str:
    trimmed = str(value or "").strip()
    stripped_telegram_prefix = False
    while True:
        next_value = trimmed
        if re.match(r"^(telegram|tg):", trimmed, re.I):
            stripped_telegram_prefix = True
            next_value = re.sub(r"^(telegram|tg):", "", trimmed, flags=re.I).strip()
        elif stripped_telegram_prefix and re.match(r"^group:", trimmed, re.I):
            next_value = re.sub(r"^group:", "", trimmed, flags=re.I).strip()
        if next_value == trimmed:
            return trimmed
        trimmed = next_value


def is_numeric_telegram_chat_id(value: str) -> bool:
    return bool(TELEGRAM_NUMERIC_CHAT_ID_RE.fullmatch(str(value or "").strip()))


def normalize_telegram_chat_id(raw: str) -> str | None:
    stripped = strip_telegram_internal_prefixes(raw)
    if not stripped:
        return None
    return stripped if is_numeric_telegram_chat_id(stripped) else None


def normalize_telegram_lookup_target(raw: str) -> str | None:
    stripped = strip_telegram_internal_prefixes(raw)
    if not stripped:
        return None
    if is_numeric_telegram_chat_id(stripped):
        return stripped
    m = re.match(r"^(?:https?://)?t\.me/([A-Za-z0-9_]+)$", stripped, re.I)
    if m and m.group(1):
        return f"@{m.group(1)}"
    if stripped.startswith("@"):
        handle = stripped[1:]
        return f"@{handle}" if handle and TELEGRAM_USERNAME_RE.fullmatch(handle) else None
    if TELEGRAM_USERNAME_RE.fullmatch(stripped):
        return f"@{stripped}"
    return None


def _resolve_telegram_chat_type(chat_id: str) -> str:
    t = str(chat_id or "").strip()
    if not t:
        return "unknown"
    if is_numeric_telegram_chat_id(t):
        return "group" if t.startswith("-") else "direct"
    return "unknown"


def parse_telegram_target(value: str) -> TelegramTarget:
    normalized = strip_telegram_internal_prefixes(value)
    topic_match = re.match(r"^(.+?):topic:(\d+)$", normalized)
    if topic_match:
        chat_id = topic_match.group(1)
        return TelegramTarget(
            chat_id=chat_id,
            message_thread_id=int(topic_match.group(2)),
            chat_type=_resolve_telegram_chat_type(chat_id),
        )
    colon_match = re.match(r"^(.+):(\d+)$", normalized)
    if colon_match:
        chat_id = colon_match.group(1)
        return TelegramTarget(
            chat_id=chat_id,
            message_thread_id=int(colon_match.group(2)),
            chat_type=_resolve_telegram_chat_type(chat_id),
        )
    return TelegramTarget(chat_id=normalized, chat_type=_resolve_telegram_chat_type(normalized))


def normalize_telegram_messaging_target(raw: str) -> str | None:
    trimmed = str(raw or "").strip()
    if not trimmed:
        return None
    prefix_stripped = re.sub(r"^(telegram|tg):", "", trimmed, flags=re.I).strip()
    parsed = parse_telegram_target(trimmed)
    normalized_chat_id = normalize_telegram_lookup_target(parsed.chat_id)
    if not normalized_chat_id:
        return None
    keep_legacy_group_prefix = bool(re.match(r"^group:", prefix_stripped, re.I))
    has_topic_suffix = bool(re.search(r":topic:\d+$", prefix_stripped, re.I))
    chat_segment = f"group:{normalized_chat_id}" if keep_legacy_group_prefix else normalized_chat_id
    if parsed.message_thread_id is None:
        return f"telegram:{chat_segment}".lower()
    thread_suffix = f":topic:{parsed.message_thread_id}" if has_topic_suffix else f":{parsed.message_thread_id}"
    return f"telegram:{chat_segment}{thread_suffix}".lower()


def looks_like_telegram_target_id(raw: str) -> bool:
    return normalize_telegram_messaging_target(raw) is not None


def parse_telegram_reply_to_message_id(value: str | int | None) -> int | None:
    if isinstance(value, int):
        return int(value)
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return int(trimmed) if re.fullmatch(r"-?\d+", trimmed) else None


def parse_telegram_thread_id(thread_id: str | int | None) -> int | None:
    if thread_id is None:
        return None
    if isinstance(thread_id, int):
        return int(thread_id)
    trimmed = str(thread_id).strip()
    if not trimmed:
        return None
    topic_match = re.match(r"^-?\d+:topic:(\d+)$", trimmed)
    if topic_match:
        return int(topic_match.group(1))
    scoped_match = re.match(r"^-?\d+:(-?\d+)$", trimmed)
    raw_thread_id = scoped_match.group(1) if scoped_match else trimmed
    return int(raw_thread_id) if re.fullmatch(r"-?\d+", raw_thread_id) else None


def telegram_plugin(*args, **kwargs):
    _ = args, kwargs
    return {
        "id": "telegram",
        "kind": "channel",
        "name": "Telegram",
        "supports": {
            "delivery": True,
            "threading": True,
            "pairing": True,
            "security_audit": True,
            "target_normalization": True,
        },
        "helpers": {
            "normalize_target": normalize_telegram_messaging_target,
            "looks_like_target_id": looks_like_telegram_target_id,
            "parse_target": parse_telegram_target,
            "parse_reply_to_message_id": parse_telegram_reply_to_message_id,
            "parse_thread_id": parse_telegram_thread_id,
        },
    }


def telegram_setup_plugin(*args, **kwargs):
    _ = args, kwargs
    return {
        "id": "telegram-setup",
        "kind": "channel-setup",
        "name": "Telegram Setup",
        "lifecycle": {"detect_legacy_state_migrations": True},
    }
