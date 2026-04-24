from __future__ import annotations

from typing import Any

from oclaw.channels.base import ChannelAdapter, InboundMessage, OutboundMessage


class WeComAdapter(ChannelAdapter):
    channel_name = "wecom"

    def parse_inbound(self, payload: dict[str, Any]) -> InboundMessage:
        user_id = str(payload.get("user_id") or payload.get("external_user_id") or "").strip()
        chat_id = str(payload.get("chat_id") or payload.get("external_chat_id") or user_id).strip()
        text = str(payload.get("text") or "").strip()
        if not user_id:
            raise ValueError("missing user_id")
        if not chat_id:
            chat_id = user_id
        is_group = bool(payload.get("is_group"))
        if is_group and chat_id == user_id:
            chat_id = f"group:unknown:{user_id}"
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        mentions_raw = payload.get("mentions")
        mentions: list[str] = []
        if isinstance(mentions_raw, list):
            mentions = [str(x).strip() for x in mentions_raw if str(x).strip()]
        attachments = payload.get("attachments") if isinstance(payload.get("attachments"), list) else []
        return InboundMessage(
            channel=self.channel_name,
            external_user_id=user_id,
            external_chat_id=chat_id,
            text=text,
            is_group=is_group,
            mentions=mentions,
            attachments=[a for a in attachments if isinstance(a, dict)],
            metadata={str(k): v for k, v in metadata.items()},
        )

    def format_outbound(self, msg: OutboundMessage) -> dict[str, Any]:
        return {
            "channel": self.channel_name,
            "chat_id": msg.external_chat_id,
            "text": msg.text,
            "attachments": msg.attachments,
            "metadata": msg.metadata,
        }


__all__ = ["WeComAdapter"]
