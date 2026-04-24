from __future__ import annotations

from .base import ChannelProvider
from .wecom import WecomProvider


def build_channel_registry() -> dict[str, ChannelProvider]:
    providers: list[ChannelProvider] = [WecomProvider()]
    return {p.name: p for p in providers}
