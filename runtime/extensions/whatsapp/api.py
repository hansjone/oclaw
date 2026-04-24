from __future__ import annotations

import re
from typing import Iterable

WHATSAPP_LEGACY_OUTBOUND_SEND_DEP_KEYS: tuple[str, ...] = ("whatsapp", "legacy_outbound_send")

_GROUP_SUFFIX = "@g.us"
_USER_SUFFIX = "@s.whatsapp.net"


def is_whatsapp_group_jid(value: str) -> bool:
    return str(value or "").strip().lower().endswith(_GROUP_SUFFIX)


def is_whatsapp_user_target(value: str) -> bool:
    v = str(value or "").strip().lower()
    return v.endswith(_USER_SUFFIX) or bool(re.fullmatch(r"\+?\d{6,20}", v))


def looks_like_whatsapp_target_id(value: str) -> bool:
    v = str(value or "").strip().lower()
    return is_whatsapp_group_jid(v) or is_whatsapp_user_target(v)


def normalize_whatsapp_target(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("whatsapp target is required")
    low = raw.lower()
    if low.endswith(_GROUP_SUFFIX) or low.endswith(_USER_SUFFIX):
        return low
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+"):
        digits = digits[1:]
    if not digits:
        raise ValueError(f"invalid whatsapp target: {value}")
    return f"{digits}{_USER_SUFFIX}"


def normalize_whatsapp_allow_from_entries(entries: Iterable[str] | None) -> tuple[str, ...]:
    out: list[str] = []
    for item in entries or ():
        try:
            out.append(normalize_whatsapp_target(str(item)))
        except Exception:
            continue
    return tuple(sorted(set(out)))

