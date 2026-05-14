"""SQLAlchemy Core table objects for incremental persistence migration."""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, MetaData, Table, Text

metadata = MetaData()

tenant = Table(
    "tenant",
    metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

bind_code = Table(
    "bind_code",
    metadata,
    Column("code", Text, primary_key=True),
    Column("tenant_id", Text, nullable=False),
    Column("role", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("used_at", Text, nullable=True),
    Column("used_by_external_user_id", Text, nullable=True),
)

app_user = Table(
    "app_user",
    metadata,
    Column("id", Text, primary_key=True),
    Column("tenant_id", Text, nullable=False),
    Column("username", Text, nullable=True),
    Column("display_name", Text, nullable=False),
    Column("role", Text, nullable=False),
    Column("password_hash", Text, nullable=True),
    Column("is_active", Integer, nullable=False, server_default="1"),
    Column("created_at", Text, nullable=False),
    Column("avatar_attachment_id", Text, nullable=True),
)

app_setting = Table(
    "app_setting",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text, nullable=False),
    Column("is_secret", Integer, nullable=False, server_default="0"),
    Column("updated_at", Text, nullable=False),
)

auth_session = Table(
    "auth_session",
    metadata,
    Column("session_token_hash", Text, primary_key=True),
    Column("tenant_id", Text, nullable=False),
    Column("user_id", Text, nullable=False),
    Column("role", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("expires_at", Text, nullable=False),
    Column("last_seen_at", Text, nullable=False),
    Column("revoked_at", Text, nullable=True),
)

chat_session = Table(
    "chat_session",
    metadata,
    Column("id", Text, primary_key=True),
    Column("title", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("last_message_at", Text, nullable=True),
)

channel_identity_v2 = Table(
    "channel_identity_v2",
    metadata,
    Column("tenant_id", Text, primary_key=True),
    Column("channel", Text, primary_key=True),
    Column("account_id", Text, primary_key=True),
    Column("external_user_id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

channel_identity = Table(
    "channel_identity",
    metadata,
    Column("tenant_id", Text, primary_key=True),
    Column("channel", Text, primary_key=True),
    Column("external_user_id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

channel_session_v2 = Table(
    "channel_session_v2",
    metadata,
    Column("tenant_id", Text, primary_key=True),
    Column("channel", Text, primary_key=True),
    Column("account_id", Text, primary_key=True),
    Column("external_chat_id", Text, primary_key=True),
    Column("external_user_id", Text, primary_key=True),
    Column("session_id", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

ui_session_owner = Table(
    "ui_session_owner",
    metadata,
    Column("session_id", Text, primary_key=True),
    Column("tenant_id", Text, nullable=False),
    Column("user_id", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

chat_message = Table(
    "chat_message",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("session_id", Text, ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False),
    Column("role", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("tool_calls", Text, nullable=True),
    Column("attachments", Text, nullable=True),
    Column("turn_uuid", Text, nullable=True),
    Column("event_type", Text, nullable=True),
    Column("event_payload", Text, nullable=True),
    Column("timestamp", Text, nullable=False),
)

tool_log = Table(
    "tool_log",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("session_id", Text, ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False),
    Column("tool_name", Text, nullable=False),
    Column("specialist", Text, nullable=False, server_default=""),
    Column("args", Text, nullable=False),
    Column("result", Text, nullable=False),
    Column("timestamp", Text, nullable=False),
    Column("duration_ms", Integer, nullable=True),
)

trace_event = Table(
    "trace_event",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("session_id", Text, nullable=False),
    Column("trace_id", Text, nullable=False),
    Column("span_id", Text, nullable=False),
    Column("parent_span_id", Text, nullable=True),
    Column("event_type", Text, nullable=False),
    Column("payload", Text, nullable=False, server_default="{}"),
    Column("timestamp", Text, nullable=False),
)

__all__ = [
    "app_user",
    "app_setting",
    "auth_session",
    "bind_code",
    "channel_identity",
    "channel_identity_v2",
    "channel_session_v2",
    "chat_message",
    "chat_session",
    "metadata",
    "tenant",
    "tool_log",
    "trace_event",
    "ui_session_owner",
]
