from __future__ import annotations

import json
import re
from typing import Any

from runtime.extensions.whatsapp.access_control import contact_phone_key
from runtime.extensions.whatsapp.api import normalize_whatsapp_target


def encode_whatsapp_outbound_source(
    *,
    kind: str = "scheduled_job",
    mention_jids: list[str] | None = None,
    mention_names: list[str] | None = None,
    mention_text_ready: bool = False,
    attachments: list[dict[str, Any]] | None = None,
    media_path: str | None = None,
) -> str:
    payload: dict[str, Any] = {"kind": str(kind or "scheduled_job")}
    jids = normalize_whatsapp_mention_jids(mention_jids)
    if jids:
        payload["mention_jids"] = jids
    names = [str(x or "").strip() for x in (mention_names or []) if str(x or "").strip()]
    if names:
        payload["mention_names"] = names
    if mention_text_ready:
        payload["mention_text_ready"] = True
    atts = [a for a in (attachments or []) if isinstance(a, dict)]
    if atts:
        payload["attachments"] = atts
    mp = str(media_path or "").strip()
    if mp:
        payload["media_path"] = mp
    return json.dumps(payload, ensure_ascii=False)


def decode_whatsapp_outbound_source(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    if text.startswith("{"):
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {"kind": text}


def normalize_whatsapp_mention_jids(raw: Any) -> list[str]:
    items: list[str] = []
    if isinstance(raw, str):
        items = re.split(r"[\s,;]+", raw)
    elif isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, str):
                items.extend(re.split(r"[\s,;]+", entry))
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        jid_raw = str(item or "").strip()
        jid = jid_raw
        low = jid_raw.lower()
        if jid and low.endswith("@lid"):
            jid = jid_raw
        elif jid and ("@" not in jid_raw):
            # Bare digits in group mentions are usually LID local parts, not phone numbers.
            if re.fullmatch(r"\d{10,20}", jid_raw):
                jid = f"{jid_raw}@lid"
            else:
                try:
                    jid = normalize_whatsapp_target(jid_raw)
                except Exception:
                    jid = jid_raw
        if not jid or jid in seen:
            continue
        seen.add(jid)
        out.append(jid)
    return out


def merge_whatsapp_mention_jids(delivery: dict[str, Any] | None, mention_jids: Any) -> dict[str, Any]:
    merged = dict(delivery or {})
    jids = normalize_whatsapp_mention_jids(mention_jids)
    if not jids:
        return merged
    wa = merged.get("whatsapp") if isinstance(merged.get("whatsapp"), dict) else {}
    wa = dict(wa)
    wa["mention_jids"] = jids
    merged["whatsapp"] = wa
    return merged


def merge_whatsapp_mention_names(delivery: dict[str, Any] | None, mention_names: Any) -> dict[str, Any]:
    merged = dict(delivery or {})
    names = [str(x or "").strip() for x in (mention_names or []) if str(x or "").strip()]
    if not names:
        return merged
    wa = merged.get("whatsapp") if isinstance(merged.get("whatsapp"), dict) else {}
    wa = dict(wa)
    wa["mention_names"] = names
    merged["whatsapp"] = wa
    return merged


def _normalize_digits(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _extract_phoneish_mentions(text: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"@([+\d][\d\s().-]{5,})", str(text or "")):
        digits = _normalize_digits(m.group(1))
        if len(digits) >= 6:
            out.append(digits)
    return out


def extract_whatsapp_mention_names(text: str) -> list[str]:
    out: list[str] = []
    # Keep it conservative: only plain @name tokens, stop at whitespace/punct.
    for m in re.finditer(r"@([^\s@]{1,64})", str(text or "")):
        token = str(m.group(1) or "").strip()
        if not token:
            continue
        # Skip phone-ish patterns; handled separately.
        if re.fullmatch(r"\+?\d[\d\s().-]{5,}", token):
            continue
        out.append(token)
    # de-dupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for name in out:
        if name not in seen:
            seen.add(name)
            deduped.append(name)
    return deduped


def infer_whatsapp_mention_jids_from_names(
    mention_names: list[str] | None,
    *,
    store: Any = None,
    tenant_id: str = "",
    account_id: str = "",
) -> list[str]:
    names = [str(x or "").strip() for x in (mention_names or []) if str(x or "").strip()]
    if not names or store is None:
        return []
    lister = getattr(store, "list_whatsapp_contacts", None)
    if not callable(lister):
        return []
    try:
        contacts = lister(tenant_id=str(tenant_id or ""), account_id=str(account_id or ""), limit=500)
    except Exception:
        return []
    by_push: dict[str, list[str]] = {}
    for row in contacts or []:
        if not isinstance(row, dict):
            continue
        jid = str(row.get("external_user_id") or "").strip()
        push = str(row.get("push_name") or "").strip()
        if jid and push:
            by_push.setdefault(push, []).append(jid)
    out: list[str] = []
    for name in names:
        hits = by_push.get(name) or []
        # Only accept unique match to avoid pinging wrong person.
        if len(hits) == 1:
            out.append(hits[0])
    return out


def _phone_digits_from_jid(jid: str) -> str:
    local = str(jid or "").split("@", 1)[0].strip()
    return _normalize_digits(local)


def infer_whatsapp_mention_jids_from_text(
    text: str,
    *,
    store: Any = None,
    tenant_id: str = "",
    account_id: str = "",
) -> list[str]:
    if store is None:
        return []
    lister = getattr(store, "list_whatsapp_contacts", None)
    if not callable(lister):
        return []
    phones = _extract_phoneish_mentions(text)
    if not phones:
        return []
    try:
        contacts = lister(tenant_id=str(tenant_id or ""), account_id=str(account_id or ""), limit=500)
    except Exception:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for phone in phones:
        for row in contacts or []:
            if not isinstance(row, dict):
                continue
            jid = str(row.get("external_user_id") or "").strip()
            if not jid or jid in seen:
                continue
            key = _normalize_digits(contact_phone_key(row))
            local = _phone_digits_from_jid(jid)
            # Accept exact/suffix matches to handle country code and formatting noise.
            if key and (key == phone or key.endswith(phone) or phone.endswith(key)):
                seen.add(jid)
                out.append(jid)
                break
            if local and (local == phone or local.endswith(phone) or phone.endswith(local)):
                seen.add(jid)
                out.append(jid)
                break
    return out


def _lookup_push_name(store: Any, *, tenant_id: str, account_id: str, jid: str) -> str:
    getter = getattr(store, "get_whatsapp_contact", None)
    if not callable(getter):
        return ""
    candidates = [str(jid or "").strip()]
    local = str(jid or "").split("@", 1)[0].strip()
    if local and f"{local}@lid" not in candidates:
        candidates.append(f"{local}@lid")
    if local and f"{local}@s.whatsapp.net" not in candidates:
        candidates.append(f"{local}@s.whatsapp.net")
    for candidate in candidates:
        if not candidate:
            continue
        try:
            row = getter(
                tenant_id=str(tenant_id or ""),
                account_id=str(account_id or ""),
                external_user_id=candidate,
            )
        except Exception:
            row = None
        if isinstance(row, dict):
            push = str(row.get("push_name") or "").strip()
            if push:
                return push
    lister = getattr(store, "list_whatsapp_contacts", None)
    if not callable(lister) or not local:
        return ""
    try:
        contacts = lister(tenant_id=str(tenant_id or ""), account_id=str(account_id or ""), limit=500)
    except Exception:
        return ""
    for row in contacts or []:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("external_user_id") or "").strip()
        if not eid:
            continue
        elocal = eid.split("@", 1)[0].strip()
        if elocal == local:
            push = str(row.get("push_name") or "").strip()
            if push:
                return push
    return ""


def mention_tag_for_jid(jid: str, *, push_name: str = "") -> str:
    name = str(push_name or "").strip()
    if name:
        return f"@{name}"
    local = str(jid or "").split("@", 1)[0].strip()
    return f"@{local}" if local else ""


def format_whatsapp_mention_text(
    text: str,
    mention_jids: list[str],
    *,
    store: Any = None,
    tenant_id: str = "",
    account_id: str = "",
    mention_names: list[str] | None = None,
) -> str:
    """Align outbound text with explicit mention JIDs; visible @ uses display name when known."""
    body = str(text or "").strip()
    jids = normalize_whatsapp_mention_jids(mention_jids)
    if not body or not jids:
        return body
    names = [str(x or "").strip() for x in (mention_names or [])]
    tags: list[str] = []
    for idx, jid in enumerate(jids):
        push_name = names[idx] if idx < len(names) and names[idx] else ""
        if not push_name and store is not None:
            push_name = _lookup_push_name(store, tenant_id=tenant_id, account_id=account_id, jid=jid)
        tag = mention_tag_for_jid(jid, push_name=push_name)
        if tag:
            tags.append(tag)
    if not tags:
        return body
    if any(tag in body for tag in tags):
        return body
    cleaned = re.sub(r"@\+?\d+(?:\s+\d+)*\s*", "", body)
    cleaned = re.sub(r"@\S+\s*", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    prefix = " ".join(tags) + " "
    return f"{prefix}{cleaned}" if cleaned else prefix.strip()


__all__ = [
    "decode_whatsapp_outbound_source",
    "encode_whatsapp_outbound_source",
    "extract_whatsapp_mention_names",
    "format_whatsapp_mention_text",
    "infer_whatsapp_mention_jids_from_names",
    "infer_whatsapp_mention_jids_from_text",
    "mention_tag_for_jid",
    "merge_whatsapp_mention_jids",
    "merge_whatsapp_mention_names",
    "normalize_whatsapp_mention_jids",
]
