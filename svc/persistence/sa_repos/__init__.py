"""SQLAlchemy-backed repository slices (incremental migration off raw SQL)."""

from __future__ import annotations

from svc.persistence.sa_repos.admin_user_stats import AdminUserStatsSaRepository
from svc.persistence.sa_repos.app_settings import AppSettingsSaRepository
from svc.persistence.sa_repos.app_users import AppUsersSaRepository
from svc.persistence.sa_repos.auth_sessions import AuthSessionsSaRepository
from svc.persistence.sa_repos.chat_messages import ChatMessagesSaRepository
from svc.persistence.sa_repos.chat_sessions import ChatSessionsSaRepository
from svc.persistence.sa_repos.session_tool_health import SessionToolHealthSaRepository
from svc.persistence.sa_repos.tenant_bind_code import BindCodeSaRepository, TenantSaRepository
from svc.persistence.sa_repos.tool_log_queries import ToolLogQueriesSaRepository
from svc.persistence.sa_repos.trace_events import TraceEventsSaRepository
from svc.persistence.sa_repos.ui_session_owner import UiSessionOwnerSaRepository

__all__ = [
    "AdminUserStatsSaRepository",
    "AppSettingsSaRepository",
    "AppUsersSaRepository",
    "AuthSessionsSaRepository",
    "BindCodeSaRepository",
    "ChatMessagesSaRepository",
    "ChatSessionsSaRepository",
    "SessionToolHealthSaRepository",
    "TenantSaRepository",
    "ToolLogQueriesSaRepository",
    "TraceEventsSaRepository",
    "UiSessionOwnerSaRepository",
]
