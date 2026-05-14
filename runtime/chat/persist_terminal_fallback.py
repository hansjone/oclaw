"""When the model run produced visible text but no ``chat_message`` row for this ``turn_uuid``."""

from __future__ import annotations

import logging
from typing import Any

_LOG = logging.getLogger(__name__)


def persist_assistant_text_if_turn_missing(
    *,
    store: Any,
    session_id: str,
    turn_uuid: str,
    final_text: str,
    log_prefix: str,
) -> bool:
    """Insert one ``assistant_text`` row if none exists for ``turn_uuid``. Return True if inserted."""
    tu = str(turn_uuid or "").strip()
    body = str(final_text or "").strip()
    if not tu or not body:
        return False
    try:
        rows = store.get_messages(session_id=str(session_id), limit=400)
        if any(
            str(getattr(m, "role", "") or "").lower() == "assistant"
            and str(getattr(m, "turn_uuid", "") or "").strip() == tu
            for m in (rows or [])
        ):
            return False
        store.add_message(
            session_id=str(session_id),
            role="assistant",
            content=body,
            turn_uuid=tu,
            event_type="assistant_text",
        )
        _LOG.warning("%s session_id=%s turn_uuid=%s chars=%d", log_prefix, str(session_id), tu, len(body))
        return True
    except Exception:
        _LOG.exception("%s_failed session_id=%s turn_uuid=%s", log_prefix, str(session_id), tu)
        return False


__all__ = ["persist_assistant_text_if_turn_missing"]
