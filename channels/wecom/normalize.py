from __future__ import annotations

from typing import Any


def _first_non_empty(*values: Any) -> str:
    for v in values:
        s = str(v or "").strip()
        if s:
            return s
    return ""


def _pick(d: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in d:
            return d.get(k)
    return None


def _extract_text(raw: dict[str, Any]) -> str:
    direct_text = _pick(raw, "text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()
    direct = _first_non_empty(
        _pick(raw, "content", "Content"),
    )
    if direct:
        return direct
    text_obj = raw.get("text")
    if isinstance(text_obj, dict):
        return _first_non_empty(_pick(text_obj, "content", "Content"))
    text_raw_obj = raw.get("text_raw")
    if isinstance(text_raw_obj, dict):
        return _first_non_empty(_pick(text_raw_obj, "content", "Content", "text"))
    content_obj = raw.get("content")
    if isinstance(content_obj, dict):
        return _first_non_empty(_pick(content_obj, "text", "content", "Content"))
    if isinstance(raw.get("msg"), dict):
        return _first_non_empty(_pick(raw.get("msg", {}), "text", "content", "Content"))
    msg_obj = raw.get("message")
    if isinstance(msg_obj, dict):
        return _first_non_empty(
            _pick(msg_obj, "text", "content", "Content"),
            _pick(msg_obj.get("text", {}), "content") if isinstance(msg_obj.get("text"), dict) else None,
        )
    payload = raw.get("payload")
    if isinstance(payload, dict):
        return _first_non_empty(
            _pick(payload, "text", "content", "Content"),
            _pick(payload.get("text", {}), "content") if isinstance(payload.get("text"), dict) else None,
        )
    return ""


def normalize_wecom_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert WeCom-like raw events into normalized gateway payload."""
    chat_id = _first_non_empty(
        _pick(raw, "chat_id", "conversation_id", "conversationId", "chatid", "roomid", "RoomId"),
        _pick(raw.get("message", {}), "chat_id", "conversation_id", "chatid")
        if isinstance(raw.get("message"), dict)
        else None,
        _pick(raw.get("chat", {}), "id", "chat_id", "chatid", "roomid")
        if isinstance(raw.get("chat"), dict)
        else None,
        _pick(raw.get("conversation", {}), "id", "chat_id", "chatid")
        if isinstance(raw.get("conversation"), dict)
        else None,
        _pick(raw.get("room", {}), "id", "roomid", "chatid")
        if isinstance(raw.get("room"), dict)
        else None,
    )
    from_obj = raw.get("from")
    user_id = _first_non_empty(
        _pick(raw, "user_id", "from_user_id", "fromUserId", "FromUserName", "userid", "external_userid"),
        from_obj if isinstance(from_obj, str) else None,
        _pick(from_obj, "userid", "user_id", "id", "from_user_id", "UserId", "userid64", "uid")
        if isinstance(from_obj, dict)
        else None,
        _pick(raw.get("sender", {}), "userid", "user_id", "id") if isinstance(raw.get("sender"), dict) else None,
        _pick(raw.get("message", {}), "from_user_id", "fromUserId") if isinstance(raw.get("message"), dict) else None,
        chat_id,
    )
    if not chat_id:
        chat_id = user_id
    text = _extract_text(raw)
    msgid = _first_non_empty(_pick(raw, "msgid", "msg_id", "id"), _pick(raw.get("message", {}), "msgid", "id"))
    agentid = _first_non_empty(_pick(raw, "agentid", "agent_id"), _pick(raw.get("message", {}), "agentid"))

    chat_type = _first_non_empty(_pick(raw, "chat_type", "conversation_type"))
    is_group = bool(raw.get("is_group")) or chat_type in ("group", "room")
    if not is_group and chat_id:
        is_group = chat_id.endswith("@chatroom")

    # If group but room id was missing, we previously fell back chat_id=user_id — same key as private 1:1.
    if is_group and chat_id == user_id:
        chat_id = f"group:unknown:{user_id}"

    return {
        "channel": "wecom",
        "user_id": user_id,
        "chat_id": chat_id or user_id,
        "text": text,
        "is_group": is_group,
        "metadata": {
            "agentid": agentid,
            "msgid": msgid,
            "source": "wecom_longconn",
            "raw": raw,
        },
    }


def normalize_wecom_event_batch(obj: Any) -> list[dict[str, Any]]:
    """Extract event list from common envelopes returned by pull APIs."""
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if not isinstance(obj, dict):
        return []
    for key in ("events", "messages", "items", "data"):
        arr = obj.get(key)
        if isinstance(arr, list):
            return [x for x in arr if isinstance(x, dict)]
    return [obj]


__all__ = ["normalize_wecom_event", "normalize_wecom_event_batch"]
