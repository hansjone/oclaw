from __future__ import annotations

from typing import Any

from oclaw.extensions.telegram import (
    normalize_telegram_messaging_target,
    parse_telegram_reply_to_message_id,
    parse_telegram_target,
    parse_telegram_thread_id,
)


def normalize_transport_target_for_channel(
    *,
    channel: str,
    to: str,
    params: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Normalize channel transport target payload for outbound paths."""
    extra: dict[str, Any] = {}
    if channel != "telegram":
        return to, extra

    normalized_target = normalize_telegram_messaging_target(to)
    parsed_target = parse_telegram_target(normalized_target or to)
    normalized_to = normalized_target or f"telegram:{parsed_target.chat_id}".lower()
    reply_to_id = parse_telegram_reply_to_message_id(params.get("replyToId"))
    thread_id = parse_telegram_thread_id(
        params.get("threadId") if params.get("threadId") is not None else parsed_target.message_thread_id
    )

    extra = {
        "target": {
            "chatId": parsed_target.chat_id,
            "chatType": parsed_target.chat_type,
            **({"messageThreadId": parsed_target.message_thread_id} if parsed_target.message_thread_id is not None else {}),
        },
        **({"threadId": thread_id} if thread_id is not None else {}),
        **({"replyToMessageId": reply_to_id} if reply_to_id is not None else {}),
    }
    return normalized_to, extra
