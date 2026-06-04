from __future__ import annotations

from dataclasses import dataclass

from svc.persistence.sqlite_store import SqliteStore


@dataclass(frozen=True)
class SessionMapResult:
    session_id: str
    scope: str  # "group" | "dm"


def get_or_create_session_for_wecom(
    store: SqliteStore,
    *,
    tenant_id: str,
    user_id: str,
    external_user_id: str,
    external_chat_id: str,
    is_group: bool,
) -> SessionMapResult:
    """Group chats share one session per external_chat_id (sentinel user key).

    Direct chats use one session per external_user_id. Identity binding always uses the real sender id.
    """
    scope = "group" if bool(is_group) else "dm"
    # For DM, external_chat_id is often contact id; we still keep it as provided.
    title = f"wecom:{scope}:{external_chat_id[:8]}"
    sid = store.get_or_create_channel_session(
        tenant_id=tenant_id,
        channel="wecom",
        external_chat_id=external_chat_id,
        external_user_id=external_user_id,
        session_title=title,
    )
    return SessionMapResult(session_id=sid, scope=scope)


__all__ = ["SessionMapResult", "get_or_create_session_for_wecom"]

