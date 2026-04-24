from __future__ import annotations

from typing import Any

from .inbound_service import process_inbound_payload

def process_inbound_payload_usecase(payload: dict[str, Any]) -> dict[str, Any]:
    """Application use-case entry for inbound gateway payload handling."""
    return process_inbound_payload(payload)


__all__ = ["process_inbound_payload_usecase", "process_inbound_payload"]

