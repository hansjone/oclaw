from __future__ import annotations

import re
from typing import Any, Literal

from runtime.extensions.whatsapp.api import normalize_whatsapp_target

AccessMode = Literal["blacklist", "whitelist"]
ListType = Literal["admin", "whitelist", "blacklist"]
ApprovalIntent = Literal["approve", "deny"]

_AFFIRMATIVE = frozenset(
    {
        "yes",
        "y",
        "approve",
        "allow",
        "add",
        "ok",
        "grant",
        "whitelist",
        "同意",
        "可以",
        "是",
        "添加",
        "通过",
    }
)
_NEGATIVE = frozenset(
    {
        "no",
        "n",
        "deny",
        "reject",
        "ignore",
        "拒绝",
        "不",
        "否",
        "忽略",
    }
)


def default_access_mode() -> AccessMode:
    return "blacklist"


def default_access_lang() -> str:
    return "en"


def is_access_allowed(*, access_mode: str, list_type: str | None) -> bool:
    lt = str(list_type or "").strip().lower()
    if lt == "admin":
        return True
    mode = str(access_mode or default_access_mode()).strip().lower()
    if mode == "whitelist":
        return lt != "blacklist"
    return lt == "whitelist"


def extract_push_name(metadata: dict[str, Any] | None) -> str:
    if not isinstance(metadata, dict):
        return ""
    for key in ("push_name", "display_name", "pushName"):
        val = metadata.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    raw = metadata.get("raw")
    if isinstance(raw, dict):
        for key in ("pushName", "push_name", "display_name"):
            val = raw.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()
    return ""


def is_whatsapp_lid_jid(jid: str) -> bool:
    return str(jid or "").strip().lower().endswith("@lid")


def phone_from_jid(jid: str) -> str:
    if is_whatsapp_lid_jid(jid):
        return ""
    base = str(jid or "").split("@", 1)[0].strip()
    digits = re.sub(r"\D", "", base)
    return digits or base


def normalize_whatsapp_phone(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("phone is required")
    digits = phone_from_jid(raw) if "@" in raw else re.sub(r"\D", "", raw.lstrip("+"))
    if len(digits) < 6:
        raise ValueError(f"invalid phone: {value}")
    return digits


def resolve_sender_phone(
    external_user_id: str,
    participant_alt: str = "",
    remote_jid_alt: str = "",
) -> str:
    for alt in (str(participant_alt or "").strip(), str(remote_jid_alt or "").strip()):
        if alt.lower().endswith("@s.whatsapp.net"):
            alt_phone = phone_from_jid(alt)
            if len(alt_phone) >= 6:
                return alt_phone
    canonical = resolve_whatsapp_sender_jid(
        external_user_id,
        {
            "raw": {
                "participantAlt": str(participant_alt or "").strip() or None,
                "remoteJidAlt": str(remote_jid_alt or "").strip() or None,
            }
        },
    )
    if str(canonical or "").lower().endswith("@s.whatsapp.net"):
        canonical_phone = phone_from_jid(canonical)
        if len(canonical_phone) >= 6:
            return canonical_phone
    if not is_whatsapp_lid_jid(external_user_id):
        raw_phone = phone_from_jid(external_user_id)
        if len(raw_phone) >= 6:
            return raw_phone
    return ""


def contact_phone_key(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    phone = str(row.get("phone") or "").strip()
    if phone:
        return phone
    return phone_from_jid(str(row.get("external_user_id") or ""))


def whatsapp_phones_match(a: str, b: str) -> bool:
    left = str(a or "").strip()
    right = str(b or "").strip()
    if not left or not right:
        return False
    try:
        return normalize_whatsapp_phone(left) == normalize_whatsapp_phone(right)
    except Exception:
        left_phone = phone_from_jid(left)
        right_phone = phone_from_jid(right)
        return bool(len(left_phone) >= 6 and left_phone == right_phone)


def jid_local_part(jid: str) -> str:
    return str(jid or "").split("@", 1)[0].split(":", 1)[0].strip().lower()


def extract_remote_jid_alt(metadata: dict[str, Any] | None) -> str:
    if not isinstance(metadata, dict):
        return ""
    raw = metadata.get("raw")
    if isinstance(raw, dict):
        for key in ("remoteJidAlt", "remote_jid_alt"):
            val = raw.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()
    return ""


def extract_participant_alt(metadata: dict[str, Any] | None) -> str:
    if not isinstance(metadata, dict):
        return ""
    raw = metadata.get("raw")
    if isinstance(raw, dict):
        for key in ("participantAlt", "participant_alt"):
            val = raw.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()
    return ""


def resolve_whatsapp_sender_jid(external_user_id: str, metadata: dict[str, Any] | None = None) -> str:
    jid = str(external_user_id or "").strip()
    participant_alt = extract_participant_alt(metadata)
    remote_jid_alt = extract_remote_jid_alt(metadata)
    low = jid.lower()
    for alt in (participant_alt, remote_jid_alt):
        if alt and low.endswith("@lid"):
            try:
                return normalize_whatsapp_target(alt)
            except Exception:
                pass
    if low.endswith("@s.whatsapp.net"):
        return low
    if low.endswith("@lid"):
        for alt in (participant_alt, remote_jid_alt):
            if alt:
                try:
                    return normalize_whatsapp_target(alt)
                except Exception:
                    pass
        return jid
    try:
        return normalize_whatsapp_target(jid)
    except Exception:
        return jid


def whatsapp_sender_lookup_jids(external_user_id: str, participant_alt: str = "") -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    canonical = resolve_whatsapp_sender_jid(
        external_user_id,
        {"raw": {"participantAlt": participant_alt}} if participant_alt else None,
    )
    for item in (external_user_id, participant_alt, canonical):
        val = str(item or "").strip()
        if val and val not in seen:
            seen.add(val)
            out.append(val)
    low = str(external_user_id or "").lower()
    if low.endswith("@lid"):
        alias = f"{jid_local_part(external_user_id)}@s.whatsapp.net"
        if alias not in seen:
            seen.add(alias)
            out.append(alias)
    return tuple(out)


def whatsapp_users_match(a: str, b: str) -> bool:
    left = str(a or "").strip()
    right = str(b or "").strip()
    if not left or not right:
        return False
    if whatsapp_phones_match(left, right):
        return True
    if left.lower() == right.lower():
        return True
    if jid_local_part(left) == jid_local_part(right):
        return True
    return False


def extract_quote_context(metadata: dict[str, Any] | None) -> dict[str, str]:
    out = {
        "stanza_id": "",
        "quoted_text": "",
        "remote_jid": "",
        "participant": "",
    }
    if not isinstance(metadata, dict):
        return out
    raw = metadata.get("raw")
    if not isinstance(raw, dict):
        return out
    out["stanza_id"] = str(
        raw.get("quotedStanzaId") or raw.get("quoted_stanza_id") or ""
    ).strip()
    out["quoted_text"] = str(
        raw.get("quotedText") or raw.get("quoted_text") or ""
    ).strip()
    out["participant"] = str(
        raw.get("quotedParticipant")
        or raw.get("quoted_participant")
        or raw.get("participant")
        or ""
    ).strip()
    for key in ("quotedRemoteJid", "quoted_remote_jid", "remoteJid"):
        val = raw.get(key)
        if val is not None and str(val).strip():
            out["remote_jid"] = str(val).strip()
            break
    return out


_PENDING_ID_IN_NOTIFY_RE = re.compile(
    r"(?:请求编号|Request)\s*[:：]\s*([0-9a-f]{16,64})",
    re.IGNORECASE,
)


def parse_pending_id_from_notify_text(text: str) -> str | None:
    m = _PENDING_ID_IN_NOTIFY_RE.search(str(text or ""))
    if not m:
        return None
    return str(m.group(1) or "").strip() or None


def admin_approval_quote_required_text(*, lang: str) -> str:
    if str(lang or "").strip().lower().startswith("zh"):
        return "请引用待审批通知消息后回复「同意」或「拒绝」。"
    return "Reply YES or NO by quoting the pending access notification."


def admin_approval_unknown_notify_text(*, lang: str) -> str:
    if str(lang or "").strip().lower().startswith("zh"):
        return "无法识别该审批请求，请引用正确的通知消息。"
    return "Cannot identify this approval request. Please quote the correct notification message."


def parse_admin_approval_intent(text: str) -> ApprovalIntent | None:
    blob = str(text or "").strip().lower()
    if not blob:
        return None
    first = re.split(r"[\s,，。.!！?？]+", blob, maxsplit=1)[0].strip()
    if first in _AFFIRMATIVE or any(tok in blob for tok in ("add to whitelist", "grant access", "添加白名单", "加入白名单")):
        return "approve"
    if first in _NEGATIVE or any(tok in blob for tok in ("do not add", "don't add", "不要添加", "不加")):
        return "deny"
    return None


def parse_admin_access_command(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    low = raw.lower()

    mode_match = re.match(r"^(?:access\s+mode|模式)\s+(blacklist|whitelist|黑名单|白名单)\b", low)
    if mode_match:
        token = mode_match.group(1)
        if token in {"黑名单", "blacklist"}:
            return {"action": "set_mode", "access_mode": "blacklist"}
        return {"action": "set_mode", "access_mode": "whitelist"}

    for verb, list_type in (
        (r"^(?:whitelist|白名单)\s+(?:add\s+)?(.+)$", "whitelist"),
        (r"^(?:blacklist|黑名单)\s+(?:add\s+)?(.+)$", "blacklist"),
        (r"^(?:admin|管理员)\s+(?:add\s+)?(.+)$", "admin"),
    ):
        m = re.match(verb, raw, flags=re.IGNORECASE)
        if m:
            target = str(m.group(1) or "").strip()
            if target:
                return {"action": "set_list", "list_type": list_type, "target": target}
    return None


def normalize_contact_jid(value: str) -> str:
    return normalize_whatsapp_target(str(value or "").strip())


def coerce_whatsapp_access_target(value: str) -> str:
    """Normalize manual contact input to canonical WhatsApp user JID from phone."""
    return normalize_whatsapp_target(normalize_whatsapp_phone(value))


def denied_reply_text(*, lang: str) -> str:
    if str(lang or "").strip().lower().startswith("zh"):
        return "无权限：您尚未获得使用此助手的授权。请联系管理员。"
    return "Access denied: you are not authorized to use this assistant. Please contact an administrator."


def admin_notify_text(
    *,
    lang: str,
    push_name: str,
    external_user_id: str,
    request_text: str,
    pending_id: str,
) -> str:
    phone = phone_from_jid(external_user_id)
    name = str(push_name or "").strip() or phone or external_user_id
    preview = str(request_text or "").strip()
    if len(preview) > 160:
        preview = preview[:157] + "..."
    if str(lang or "").strip().lower().startswith("zh"):
        return (
            f"[oclaw] 未授权用户请求访问\n"
            f"用户: {name}\n"
            f"ID: {external_user_id}\n"
            f"消息: {preview or '(empty)'}\n"
            f"请求编号: {pending_id}\n"
            f"请引用本条消息回复「同意」或「拒绝」。"
        )
    return (
        f"[oclaw] Unauthorized access request\n"
        f"User: {name}\n"
        f"ID: {external_user_id}\n"
        f"Message: {preview or '(empty)'}\n"
        f"Request: {pending_id}\n"
        f"Reply YES or NO by quoting this message."
    )


def admin_approval_result_text(*, lang: str, approved: bool, push_name: str, external_user_id: str) -> str:
    name = str(push_name or "").strip() or phone_from_jid(external_user_id) or external_user_id
    if str(lang or "").strip().lower().startswith("zh"):
        if approved:
            return f"已将 {name} ({external_user_id}) 加入白名单。"
        return f"已忽略 {name} ({external_user_id}) 的访问请求。"
    if approved:
        return f"Whitelisted {name} ({external_user_id})."
    return f"Ignored access request from {name} ({external_user_id})."
