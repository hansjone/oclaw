from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class InboundMessage:
    channel: str
    external_user_id: str
    external_chat_id: str
    text: str
    is_group: bool = False
    mentions: list[str] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundMessage:
    external_chat_id: str
    text: str
    attachments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ChannelAdapter(Protocol):
    channel_name: str

    def parse_inbound(self, payload: dict[str, Any]) -> InboundMessage:
        raise NotImplementedError

    def format_outbound(self, msg: OutboundMessage) -> dict[str, Any]:
        raise NotImplementedError


def safe_json_loads(raw: str) -> dict[str, Any]:
    try:
        obj = json.loads(raw or "")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


__all__ = ["InboundMessage", "OutboundMessage", "ChannelAdapter", "safe_json_loads"]
