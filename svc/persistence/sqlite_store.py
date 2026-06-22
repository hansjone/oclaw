from __future__ import annotations

import base64
import json
import logging
import os
import re
import sqlite3
import sys
import hashlib
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError

from svc.persistence.pg_adapter import PgConnShim, connect_postgres
from svc.persistence.pg_compat import scrub_nul_bytes_from_jsonable, scrub_nul_bytes_from_text

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_LOG = logging.getLogger(__name__)


def _chat_message_persist_log_enabled() -> bool:
    v = str(os.getenv("AIA_LOG_CHAT_MESSAGE_PERSIST") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


# 内置模型配置（不可删除；rule 不在设置界面展示）
LLM_BUILTIN_OLLAMA_PROFILE_ID = "00000001-0000-4000-8000-000000000001"
LLM_BUILTIN_RULE_PROFILE_ID = "00000001-0000-4000-8000-000000000002"
_BUILTIN_OLLAMA_MODEL_SEED = "qwen2.5:7b"
_BUILTIN_OLLAMA_BASE_SEED = "http://127.0.0.1:11434/v1"

# 与 src.agents.specialists.AGENT_PROFILE_BINDINGS_KEY 保持一致（避免 sqlite_store 导入 agents 环依赖）
_MODEL_BINDINGS_KEY = "agent_profile_bindings"


def is_administrator_model_pool(username: str | None) -> bool:
    """控制台「全局模型池」仅 administrator 用户名使用；其余用户各自一套 profile + active + bindings。"""
    return str(username or "").strip().lower() == "administrator"


def active_llm_profile_setting_key(user_id: str, username: str | None) -> str:
    return "active_llm_profile_id" if is_administrator_model_pool(username) else f"active_llm_profile_id:{user_id}"


def agent_profile_bindings_setting_key(user_id: str, username: str | None) -> str:
    return _MODEL_BINDINGS_KEY if is_administrator_model_pool(username) else f"{_MODEL_BINDINGS_KEY}:{user_id}"


def _tool_row_assistant_message_id(tool_calls_text: str | None) -> int | None:
    if not tool_calls_text:
        return None
    try:
        meta = json.loads(tool_calls_text)
        if isinstance(meta, dict):
            aid = meta.get("assistant_message_id")
            if aid is not None:
                return int(aid)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


def _trim_messages_start_index(rows: list[Any], keep_last: int) -> int | None:
    """计算应保留的起始索引，避免 tool 消息与对应 assistant 消息断链。"""
    n = len(rows)
    if n <= keep_last:
        return None
    start = n - keep_last
    id_list = [int(r["id"]) for r in rows]
    id_to_index = {mid: i for i, mid in enumerate(id_list)}
    while 0 <= start < n:
        r = rows[start]
        if str(r["role"]) != "tool":
            break
        aid = _tool_row_assistant_message_id(r["tool_calls"])
        if aid is None:
            break
        j = id_to_index.get(aid)
        if j is None or j >= start:
            break
        start = j
    return start


@dataclass(frozen=True)
class ChatSession:
    id: str
    title: str
    created_at: str
    last_message_at: str | None = None


@dataclass(frozen=True)
class ChatMessage:
    id: int
    session_id: str
    role: str
    content: str
    tool_calls: Optional[str]
    timestamp: str
    attachments: Optional[str] = None
    turn_uuid: Optional[str] = None
    event_type: Optional[str] = None
    event_payload: Optional[str] = None


@dataclass(frozen=True)
class SessionMessagesMeta:
    session_id: str
    message_count: int
    last_message_id: int | None
    last_message_at: str | None

    @property
    def revision_key(self) -> tuple[str, int, int | None, str | None]:
        return (self.session_id, self.message_count, self.last_message_id, self.last_message_at)


@dataclass(frozen=True)
class SessionsListMeta:
    session_count: int
    latest_activity_at: str | None

    @property
    def revision_key(self) -> tuple[int, str | None]:
        return (self.session_count, self.latest_activity_at)


@dataclass(frozen=True)
class OclawTask:
    id: str
    tenant_id: str
    session_id: str
    task_type: str
    status: str
    payload: str
    result: str
    attempt_count: int
    claimed_by: str | None
    lease_expires_at: str | None
    last_error: str
    created_at: str
    updated_at: str
    finished_at: str | None


@dataclass(frozen=True)
class OclawRun:
    run_id: str
    tenant_id: str
    session_id: str
    status: str
    payload: str
    created_at: str
    updated_at: str


class _CryptoError(RuntimeError):
    pass


def _fernet() -> Any | None:
    """Best-effort Fernet cipher for non-Windows secret storage.

    Enable by setting AIA_ASSISTANT_MASTER_KEY (any non-empty string).
    """
    mk = (os.getenv("AIA_ASSISTANT_MASTER_KEY") or "").strip()
    if not mk:
        return None
    try:
        from cryptography.fernet import Fernet  # type: ignore
    except Exception:
        return None
    # Derive a stable 32-byte key from master key string.
    digest = hashlib.sha256(mk.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    try:
        return Fernet(key)
    except Exception:
        return None


def _dpapi_encrypt(plain: bytes) -> bytes:
    if sys.platform != "win32":
        raise _CryptoError("DPAPI 仅支持 Windows")

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    in_blob = DATA_BLOB()
    in_blob.cbData = len(plain)
    buf = ctypes.create_string_buffer(plain, len(plain))
    in_blob.pbData = ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))

    out_blob = DATA_BLOB()
    res = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0x1,
        ctypes.byref(out_blob),
    )
    if not res:
        raise _CryptoError(f"CryptProtectData 失败: {ctypes.get_last_error()}")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _dpapi_decrypt(cipher: bytes) -> bytes:
    if sys.platform != "win32":
        raise _CryptoError("DPAPI 仅支持 Windows")

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    in_blob = DATA_BLOB()
    in_blob.cbData = len(cipher)
    buf = ctypes.create_string_buffer(cipher, len(cipher))
    in_blob.pbData = ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))

    out_blob = DATA_BLOB()
    res = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0x1,
        ctypes.byref(out_blob),
    )
    if not res:
        raise _CryptoError(f"CryptUnprotectData 失败: {ctypes.get_last_error()}")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _encode_secret(plain_text: str) -> str:
    plain_bytes = plain_text.encode("utf-8")
    try:
        enc = _dpapi_encrypt(plain_bytes)
        return "dpapi:" + base64.b64encode(enc).decode("ascii")
    except Exception:
        f = _fernet()
        if f is not None:
            try:
                token = f.encrypt(plain_bytes)
                return "fernet:" + token.decode("ascii")
            except Exception:
                pass
        return "b64:" + base64.b64encode(plain_bytes).decode("ascii")


def _decode_secret(secret_text: str) -> str:
    if secret_text.startswith("dpapi:"):
        cipher = base64.b64decode(secret_text[len("dpapi:") :].encode("ascii"))
        plain = _dpapi_decrypt(cipher)
        return plain.decode("utf-8")
    if secret_text.startswith("fernet:"):
        token = secret_text[len("fernet:") :].strip().encode("ascii")
        f = _fernet()
        if f is None:
            raise _CryptoError("missing AIA_ASSISTANT_MASTER_KEY or cryptography for fernet secret")
        plain = f.decrypt(token)
        return plain.decode("utf-8")
    if secret_text.startswith("b64:"):
        plain = base64.b64decode(secret_text[len("b64:") :].encode("ascii"))
        return plain.decode("utf-8")
    raise _CryptoError("未知的密钥编码格式")


class SqliteStore:
    @staticmethod
    def _cap_json_for_log(obj: Any, *, max_chars: int, keep_keys: tuple[str, ...] = ("ok", "error_code", "error")) -> Any:
        cap = max(2000, int(max_chars or 0))
        try:
            blob = json.dumps(obj, ensure_ascii=False, default=str)
        except Exception:
            blob = json.dumps({"_log_cap": True, "repr": repr(obj)}, ensure_ascii=False)
        if len(blob) <= cap:
            return obj
        slim: dict[str, Any] = {"_log_cap": True, "bytes": len(blob)}
        if isinstance(obj, dict):
            for k in keep_keys:
                if k in obj:
                    slim[k] = obj.get(k)
        slim["preview"] = blob[: min(cap, 4000)]
        return slim
    def __init__(self, db_path: str | Path | None = None, *, postgres_url: str | None = None) -> None:
        if postgres_url:
            self._postgres_url = str(postgres_url).strip()
            self._use_pg = True
            self.db_path = self._postgres_url
        else:
            if db_path is None:
                raise TypeError("SqliteStore requires db_path unless postgres_url= is set")
            self.db_path = str(db_path)
            self._postgres_url = ""
            self._use_pg = False
        try:
            self._init_db()
        except Exception as exc:
            if self._use_pg:
                raise RuntimeError(
                    "Assistant PostgreSQL initialization failed (connection, permissions, or missing tables). "
                    "Apply schema with `alembic upgrade head` (or `svc/persistence/ddl/postgresql_bootstrap.sql`), "
                    "verify AIA_ASSISTANT_DATABASE_URL, and inspect the chained exception."
                ) from exc
            raise

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        if self._use_pg:
            raw = connect_postgres(self._postgres_url)
            shim = PgConnShim(raw)
            try:
                yield shim
                raw.commit()
            except BaseException:
                raw.rollback()
                raise
            finally:
                raw.close()
            return
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _shared_sa_engine(self):
        """SQLAlchemy engine for the same database as :meth:`_connect` (per SQLite file or PostgreSQL URL)."""
        from svc.persistence.db.engine import engine_for_sqlite_file, get_assistant_engine

        if self._use_pg:
            return get_assistant_engine()
        return engine_for_sqlite_file(str(self.db_path))

    def _app_settings_repo(self):
        """Lazily construct SA repository for ``app_setting`` (same DB URL as raw :meth:`_connect`)."""
        from svc.persistence.sa_repos.app_settings import AppSettingsSaRepository

        r = self.__dict__.get("_app_settings_sa")
        if r is None:
            r = AppSettingsSaRepository(self._shared_sa_engine())
            self.__dict__["_app_settings_sa"] = r
        return r

    def _auth_sessions_repo(self):
        """Lazily construct SA repository for ``auth_session`` (same DB URL as raw :meth:`_connect`)."""
        from svc.persistence.sa_repos.auth_sessions import AuthSessionsSaRepository

        r = self.__dict__.get("_auth_sessions_sa")
        if r is None:
            r = AuthSessionsSaRepository(self._shared_sa_engine())
            self.__dict__["_auth_sessions_sa"] = r
        return r

    def _chat_sessions_repo(self):
        """Lazily construct SA repository for ``chat_session`` / ``ui_session_owner`` list paths."""
        from svc.persistence.sa_repos.chat_sessions import ChatSessionsSaRepository

        r = self.__dict__.get("_chat_sessions_sa")
        if r is None:
            r = ChatSessionsSaRepository(self._shared_sa_engine())
            self.__dict__["_chat_sessions_sa"] = r
        return r

    def _ui_session_owner_repo(self):
        from svc.persistence.sa_repos.ui_session_owner import UiSessionOwnerSaRepository

        r = self.__dict__.get("_ui_session_owner_sa")
        if r is None:
            r = UiSessionOwnerSaRepository(self._shared_sa_engine())
            self.__dict__["_ui_session_owner_sa"] = r
        return r

    def _tenant_repo(self):
        from svc.persistence.sa_repos.tenant_bind_code import TenantSaRepository

        r = self.__dict__.get("_tenant_sa")
        if r is None:
            r = TenantSaRepository(self._shared_sa_engine())
            self.__dict__["_tenant_sa"] = r
        return r

    def _bind_code_repo(self):
        from svc.persistence.sa_repos.tenant_bind_code import BindCodeSaRepository

        r = self.__dict__.get("_bind_code_sa")
        if r is None:
            r = BindCodeSaRepository(self._shared_sa_engine())
            self.__dict__["_bind_code_sa"] = r
        return r

    def _app_users_repo(self):
        from svc.persistence.sa_repos.app_users import AppUsersSaRepository

        r = self.__dict__.get("_app_users_sa")
        if r is None:
            r = AppUsersSaRepository(self._shared_sa_engine())
            self.__dict__["_app_users_sa"] = r
        return r

    def _chat_messages_repo(self):
        """Lazily construct SA repository for ``chat_message`` hot paths."""
        from svc.persistence.sa_repos.chat_messages import ChatMessagesSaRepository

        r = self.__dict__.get("_chat_messages_sa")
        if r is None:
            r = ChatMessagesSaRepository(self._shared_sa_engine())
            self.__dict__["_chat_messages_sa"] = r
        return r

    def _admin_user_stats_repo(self):
        from svc.persistence.sa_repos.admin_user_stats import AdminUserStatsSaRepository

        r = self.__dict__.get("_admin_user_stats_sa")
        if r is None:
            r = AdminUserStatsSaRepository(self._shared_sa_engine())
            self.__dict__["_admin_user_stats_sa"] = r
        return r

    def _session_tool_health_repo(self):
        from svc.persistence.sa_repos.session_tool_health import SessionToolHealthSaRepository

        r = self.__dict__.get("_session_tool_health_sa")
        if r is None:
            r = SessionToolHealthSaRepository(self._shared_sa_engine())
            self.__dict__["_session_tool_health_sa"] = r
        return r

    def _tool_log_queries_repo(self):
        from svc.persistence.sa_repos.tool_log_queries import ToolLogQueriesSaRepository

        r = self.__dict__.get("_tool_log_queries_sa")
        if r is None:
            r = ToolLogQueriesSaRepository(self._shared_sa_engine())
            self.__dict__["_tool_log_queries_sa"] = r
        return r

    def _trace_events_repo(self):
        from svc.persistence.sa_repos.trace_events import TraceEventsSaRepository

        r = self.__dict__.get("_trace_events_sa")
        if r is None:
            r = TraceEventsSaRepository(self._shared_sa_engine())
            self.__dict__["_trace_events_sa"] = r
        return r

    def _init_db(self) -> None:
        if self._use_pg:
            self._init_db_postgresql()
            return
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_session (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_message_at TEXT
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_session_activity ON chat_session(COALESCE(last_message_at, created_at) DESC, created_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_user (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    username TEXT,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    password_hash TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE
                );
                """
            )
            user_cols = {row[1] for row in conn.execute("PRAGMA table_info(app_user)").fetchall()}
            if "username" not in user_cols:
                conn.execute("ALTER TABLE app_user ADD COLUMN username TEXT")
            if "password_hash" not in user_cols:
                conn.execute("ALTER TABLE app_user ADD COLUMN password_hash TEXT")
            if "is_active" not in user_cols:
                conn.execute("ALTER TABLE app_user ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
            if "avatar_attachment_id" not in user_cols:
                conn.execute("ALTER TABLE app_user ADD COLUMN avatar_attachment_id TEXT")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_app_user_tenant_username ON app_user(tenant_id, username)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_identity (
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    external_user_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, channel, external_user_id),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_identity_v2 (
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    external_user_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, channel, account_id, external_user_id),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bind_code (
                    code TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    used_at TEXT,
                    used_by_external_user_id TEXT,
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_session (
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    external_chat_id TEXT NOT NULL,
                    external_user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, channel, external_chat_id, external_user_id),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_session_v2 (
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    external_chat_id TEXT NOT NULL,
                    external_user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, channel, account_id, external_chat_id, external_user_id),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_channel_account (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    config TEXT NOT NULL DEFAULT '{}',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, user_id, channel, account_id),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_channel_account_channel_account ON user_channel_account(channel, account_id, is_active)"
            )
            uca_cols = {row[1] for row in conn.execute("PRAGMA table_info(user_channel_account)").fetchall()}
            if "name" not in uca_cols:
                conn.execute("ALTER TABLE user_channel_account ADD COLUMN name TEXT NOT NULL DEFAULT ''")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS whatsapp_known_group (
                    tenant_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    group_jid TEXT NOT NULL,
                    group_name TEXT NOT NULL DEFAULT '',
                    last_seen_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, account_id, group_jid)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS whatsapp_alert_binding (
                    tenant_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    group_jid TEXT NOT NULL,
                    group_name TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, account_id)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_outbound_message (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT '',
                    channel TEXT NOT NULL,
                    account_id TEXT NOT NULL DEFAULT '',
                    chat_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    source TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    sent_at TEXT,
                    error TEXT NOT NULL DEFAULT ''
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_channel_outbound_pending ON channel_outbound_message(channel, account_id, status, created_at)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS todo_item (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    assignee_user_id TEXT,
                    title TEXT NOT NULL,
                    due_at TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(owner_user_id) REFERENCES app_user(id) ON DELETE CASCADE,
                    FOREIGN KEY(assignee_user_id) REFERENCES app_user(id) ON DELETE SET NULL
                );
                """
            )
            sess_cols = {row[1] for row in conn.execute("PRAGMA table_info(chat_session)").fetchall()}
            if "last_message_at" not in sess_cols:
                conn.execute("ALTER TABLE chat_session ADD COLUMN last_message_at TEXT")
                conn.execute(
                    """
                    UPDATE chat_session SET last_message_at = (
                        SELECT MAX(timestamp) FROM chat_message
                        WHERE chat_message.session_id = chat_session.id
                    )
                    """
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_message (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_calls TEXT,
                    attachments TEXT,
                    turn_uuid TEXT,
                    event_type TEXT,
                    event_payload TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE
                );
                """
            )
            msg_cols = {row[1] for row in conn.execute("PRAGMA table_info(chat_message)").fetchall()}
            if "turn_uuid" not in msg_cols:
                conn.execute("ALTER TABLE chat_message ADD COLUMN turn_uuid TEXT")
            if "event_type" not in msg_cols:
                conn.execute("ALTER TABLE chat_message ADD COLUMN event_type TEXT")
            if "event_payload" not in msg_cols:
                conn.execute("ALTER TABLE chat_message ADD COLUMN event_payload TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_message_session_turn_uuid ON chat_message(session_id, turn_uuid)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ui_session_owner (
                    session_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE,
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ui_session_owner_tenant_user ON ui_session_owner(tenant_id, user_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ui_session_owner_tenant_user_session ON ui_session_owner(tenant_id, user_id, session_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ui_session_owner_tenant_session ON ui_session_owner(tenant_id, session_id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_workspace_path_allowlist (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    extra_roots TEXT NOT NULL DEFAULT '',
                    allow_any_path INTEGER NOT NULL DEFAULT 0,
                    allow_high_risk_public_tools INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, user_id),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );
                """
            )
            uw_cols = {row[1] for row in conn.execute("PRAGMA table_info(user_workspace_path_allowlist)").fetchall()}
            if "allow_high_risk_public_tools" not in uw_cols:
                conn.execute(
                    "ALTER TABLE user_workspace_path_allowlist ADD COLUMN allow_high_risk_public_tools INTEGER NOT NULL DEFAULT 0"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_session (
                    session_token_hash TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    revoked_at TEXT,
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_session_user_expires ON auth_session(user_id, expires_at)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS role_permission (
                    role TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (role, permission)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_permission (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, user_id, permission),
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_tenant_id TEXT NOT NULL,
                    actor_user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '{}',
                    timestamp TEXT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_admin_audit_actor_ts ON admin_audit_log(actor_user_id, timestamp DESC)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attachment_acl (
                    attachment_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (attachment_id, tenant_id, user_id, session_id, source),
                    FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE,
                    FOREIGN KEY(tenant_id) REFERENCES tenant(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_attachment_acl_tenant_attachment ON attachment_acl(tenant_id, attachment_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_attachment_acl_user_attachment ON attachment_acl(tenant_id, user_id, attachment_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_attachment_acl_session_attachment ON attachment_acl(session_id, attachment_id, created_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    specialist TEXT NOT NULL DEFAULT '',
                    args TEXT NOT NULL,
                    result TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    duration_ms INTEGER,
                    FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE
                );
                """
            )
            cols = {row[1] for row in conn.execute("PRAGMA table_info(tool_log)").fetchall()}
            if "duration_ms" not in cols:
                conn.execute("ALTER TABLE tool_log ADD COLUMN duration_ms INTEGER")
            if "specialist" not in cols:
                conn.execute("ALTER TABLE tool_log ADD COLUMN specialist TEXT NOT NULL DEFAULT ''")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_plugin (
                    plugin_name TEXT NOT NULL,
                    plugin_version TEXT NOT NULL,
                    entry_point TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (plugin_name, entry_point)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mcp_server_registry (
                    server_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    version TEXT NOT NULL DEFAULT '',
                    entry_command TEXT NOT NULL DEFAULT '',
                    entry_args TEXT NOT NULL DEFAULT '[]',
                    env_schema TEXT NOT NULL DEFAULT '{}',
                    required_permissions TEXT NOT NULL DEFAULT '[]',
                    risk_level TEXT NOT NULL DEFAULT 'high',
                    timeout_s REAL NOT NULL DEFAULT 30,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mcp_server_installation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_code TEXT NOT NULL DEFAULT '',
                    detail TEXT NOT NULL DEFAULT '{}',
                    install_command TEXT NOT NULL DEFAULT '',
                    timestamp TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mcp_server_health (
                    server_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '{}',
                    checked_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mcp_server_tool (
                    server_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    parameters TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (server_id, tool_name)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_setting (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    is_secret INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_chunk (
                    chunk_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_embedding (
                    chunk_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    vector_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (chunk_id, model),
                    FOREIGN KEY(chunk_id) REFERENCES knowledge_chunk(chunk_id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_item (
                    memory_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'memory',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_vector (
                    memory_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    vector_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (memory_id, model),
                    FOREIGN KEY(memory_id) REFERENCES memory_item(memory_id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_hit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    memory_id TEXT,
                    query_text TEXT NOT NULL,
                    score REAL NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'memory',
                    timestamp TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_item_tenant_user_updated ON memory_item(tenant_id, user_id, updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_hit_log_tenant_user_ts ON memory_hit_log(tenant_id, user_id, timestamp DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_item_session_updated ON memory_item(session_id, updated_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oclaw_task (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    task_type TEXT NOT NULL DEFAULT 'async_turn',
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    result TEXT NOT NULL DEFAULT '{}',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    claimed_by TEXT,
                    lease_expires_at TEXT,
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oclaw_run (
                    run_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oclaw_attempt (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    attempt_no INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_oclaw_task_status_updated ON oclaw_task(status, updated_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_oclaw_task_tenant_session ON oclaw_task(tenant_id, session_id, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_oclaw_run_tenant_session ON oclaw_run(tenant_id, session_id, updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_oclaw_attempt_run_no ON oclaw_attempt(run_id, attempt_no)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_source_updated ON knowledge_chunk(source, updated_at)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    specialist TEXT NOT NULL,
                    task_kind TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    timestamp TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_eval_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    specialist TEXT NOT NULL,
                    task_kind TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    cost_hint REAL NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    timestamp TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trace_event (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    span_id TEXT NOT NULL,
                    parent_span_id TEXT,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    timestamp TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trace_event_session_id_id ON trace_event(session_id, id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_profile (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    model TEXT,
                    base_url TEXT,
                    api_key TEXT,
                    updated_at TEXT NOT NULL
                );
                """
            )
            prof_cols = {row[1] for row in conn.execute("PRAGMA table_info(llm_profile)").fetchall()}
            if "is_builtin" not in prof_cols:
                conn.execute("ALTER TABLE llm_profile ADD COLUMN is_builtin INTEGER NOT NULL DEFAULT 0")
            if "hide_in_ui" not in prof_cols:
                conn.execute("ALTER TABLE llm_profile ADD COLUMN hide_in_ui INTEGER NOT NULL DEFAULT 0")
            if "owner_user_id" not in prof_cols:
                conn.execute("ALTER TABLE llm_profile ADD COLUMN owner_user_id TEXT")
            if "thinking_mode_enabled" not in prof_cols:
                conn.execute("ALTER TABLE llm_profile ADD COLUMN thinking_mode_enabled INTEGER NOT NULL DEFAULT 0")
            if "reasoning_effort" not in prof_cols:
                conn.execute("ALTER TABLE llm_profile ADD COLUMN reasoning_effort TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_profile_user_grant (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by_user_id TEXT,
                    UNIQUE(tenant_id, profile_id, user_id),
                    FOREIGN KEY(profile_id) REFERENCES llm_profile(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES app_user(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_llm_profile_grant_user ON llm_profile_user_grant(tenant_id, user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_llm_profile_grant_profile ON llm_profile_user_grant(tenant_id, profile_id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_profile_tenant_grant (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by_user_id TEXT,
                    UNIQUE(tenant_id, profile_id),
                    FOREIGN KEY(profile_id) REFERENCES llm_profile(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_llm_profile_tenant_grant ON llm_profile_tenant_grant(tenant_id, profile_id)"
            )
            self._seed_builtin_llm_profiles(conn)
            self._seed_default_permissions(conn)
            conn.execute(
                """
                UPDATE llm_profile SET model = ?, updated_at = ?
                WHERE id = ? AND (model IS NULL OR model = 'llama3.2')
                """,
                (_BUILTIN_OLLAMA_MODEL_SEED, utc_now_iso(), LLM_BUILTIN_OLLAMA_PROFILE_ID),
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_message_session_id_id ON chat_message(session_id, id)"
            )
            # 若历史上曾在未开启 foreign_keys 的连接里删除过 ``chat_session``，或表创建时未带外键，
            # 会留下指向已不存在会话的行。每次初始化库时做一次幂等清理。
            self._prune_rows_for_missing_chat_session(conn)

        self._prune_orphan_chat_message_and_tool_log_outside_db_transaction()

    def _init_db_postgresql(self) -> None:
        """PostgreSQL: tables from Alembic migration; run seeds and housekeeping."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS whatsapp_known_group (
                    tenant_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    group_jid TEXT NOT NULL,
                    group_name TEXT NOT NULL DEFAULT '',
                    last_seen_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, account_id, group_jid)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS whatsapp_alert_binding (
                    tenant_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    group_jid TEXT NOT NULL,
                    group_name TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, account_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_outbound_message (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT '',
                    channel TEXT NOT NULL,
                    account_id TEXT NOT NULL DEFAULT '',
                    chat_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    source TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    sent_at TEXT,
                    error TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_channel_outbound_pending ON channel_outbound_message(channel, account_id, status, created_at)"
            )
            self._seed_builtin_llm_profiles(conn)
            self._seed_default_permissions(conn)
            conn.execute(
                """
                UPDATE llm_profile SET model = ?, updated_at = ?
                WHERE id = ? AND (model IS NULL OR model = 'llama3.2')
                """,
                (_BUILTIN_OLLAMA_MODEL_SEED, utc_now_iso(), LLM_BUILTIN_OLLAMA_PROFILE_ID),
            )
            self._prune_rows_for_missing_chat_session(conn)

        # PostgreSQL: ``chat_message`` / ``tool_log`` reference ``chat_session`` with FK.
        # Do **not** run :meth:`_prune_orphan_chat_message_and_tool_log_outside_db_transaction` on
        # every process start: the legacy ``NOT IN (SELECT id FROM chat_session)`` housekeeping
        # can race concurrent inserts or interact badly with NULL / visibility, making admin chat
        # ``loadMessages`` return empty right after a turn (bubbles flash then vanish).

    def _prune_orphan_chat_message_and_tool_log_outside_db_transaction(self) -> None:
        """Remove orphan ``chat_message`` / ``tool_log`` rows (must not run inside raw ``_connect`` on SQLite).

        SQLAlchemy uses its own pooled connection; running these deletes while a raw sqlite3 write
        transaction is open would deadlock with ``database is locked``.
        """
        self._chat_messages_repo().delete_messages_where_session_missing()
        self._tool_log_queries_repo().delete_tool_logs_where_session_missing()

    def _prune_rows_for_missing_chat_session(self, conn: Any) -> None:
        sid_alive = "(SELECT id FROM chat_session)"
        conn.execute(
            "DELETE FROM oclaw_attempt WHERE run_id NOT IN (SELECT run_id FROM oclaw_run) "
            f"OR run_id IN (SELECT run_id FROM oclaw_run WHERE session_id NOT IN {sid_alive})"
        )
        conn.execute(f"DELETE FROM oclaw_run WHERE session_id NOT IN {sid_alive}")
        conn.execute(f"DELETE FROM oclaw_task WHERE session_id NOT IN {sid_alive}")
        conn.execute(f"DELETE FROM attachment_acl WHERE session_id NOT IN {sid_alive}")

    def _seed_builtin_llm_profiles(self, conn: Any) -> None:
        ts = utc_now_iso()
        conn.execute(
            """
            INSERT OR IGNORE INTO llm_profile
                (id, name, mode, model, base_url, api_key, updated_at, is_builtin, hide_in_ui, owner_user_id)
            VALUES (?, ?, 'ollama', ?, ?, NULL, ?, 1, 0, NULL)
            """,
            (
                LLM_BUILTIN_OLLAMA_PROFILE_ID,
                "本地 Ollama（默认）",
                _BUILTIN_OLLAMA_MODEL_SEED,
                _BUILTIN_OLLAMA_BASE_SEED,
                ts,
            ),
        )

    def _seed_default_permissions(self, conn: Any) -> None:
        ts = utc_now_iso()
        defaults = {
            "owner": {
                "admin:read",
                "admin:user:read",
                "admin:user:write",
                "admin:user:delete",
                "admin:tenant:read",
                "admin:tenant:write",
                "admin:workspace_paths:read",
                "admin:workspace_paths:write",
                "admin:memory:write",
                "admin:runtime:write",
            },
            "admin": {
                "admin:read",
                "admin:user:read",
                "admin:user:write",
                "admin:user:delete",
                "admin:tenant:read",
                "admin:tenant:write",
                "admin:workspace_paths:read",
                "admin:workspace_paths:write",
                "admin:memory:write",
                "admin:runtime:write",
            },
            "member": {
                "admin:read",
                "admin:tenant:read",
                "admin:workspace_paths:read",
                "admin:workspace_paths:write",
            },
            "guest": {"admin:read"},
        }
        for role, permissions in defaults.items():
            for perm in permissions:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO role_permission(role, permission, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (role, perm, ts),
                )
        conn.execute(
            """
            INSERT OR IGNORE INTO llm_profile
                (id, name, mode, model, base_url, api_key, updated_at, is_builtin, hide_in_ui, owner_user_id)
            VALUES (?, ?, 'rule', NULL, NULL, NULL, ?, 1, 1, NULL)
            """,
            (LLM_BUILTIN_RULE_PROFILE_ID, "内置规则兜底", ts),
        )

    def create_session(self, title: str) -> ChatSession:
        session_id = uuid.uuid4().hex
        created_at = utc_now_iso()
        self._chat_sessions_repo().insert_chat_session(
            session_id=session_id, title=title, created_at=created_at
        )
        return ChatSession(id=session_id, title=title, created_at=created_at, last_message_at=None)

    def create_session_for_user(self, *, title: str, tenant_id: str, user_id: str) -> ChatSession:
        s = self.create_session(title)
        try:
            self._ui_session_owner_repo().upsert_replace(
                session_id=str(s.id),
                tenant_id=str(tenant_id),
                user_id=str(user_id),
                created_at=utc_now_iso(),
            )
        except IntegrityError:
            # ``chat_session`` is already committed; without ``ui_session_owner`` the session is invisible
            # to ``list_sessions_for_user`` / ``get_session_for_user`` (INNER JOIN). PostgreSQL enforces
            # FK from ``ui_session_owner`` to ``tenant`` / ``app_user``; a failed owner row leaves a
            # "ghost" session that looks like PG-specific data loss vs SQLite (weaker FK history).
            try:
                self.delete_session(str(s.id))
            except Exception:
                pass
            raise
        return s

    def ensure_ui_session_owner(self, *, session_id: str, tenant_id: str, user_id: str) -> None:
        self._ui_session_owner_repo().insert_ignore(
            session_id=str(session_id),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            created_at=utc_now_iso(),
        )

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self._chat_sessions_repo().fetch_chat_session_by_id(session_id=session_id)

    def get_ui_session_owner(self, *, session_id: str) -> dict[str, Any] | None:
        sid = str(session_id or "").strip()
        if not sid:
            return None
        row = self._ui_session_owner_repo().fetch_by_session_id(session_id=sid)
        if not row:
            return None
        return {
            "tenant_id": str(row["tenant_id"] or ""),
            "user_id": str(row["user_id"] or ""),
            "created_at": str(row["created_at"] or ""),
        }

    def backfill_orphan_chat_sessions_for_user(self, *, tenant_id: str, user_id: str) -> int:
        """将**当前库中所有**尚无 ``ui_session_owner`` 的 ``chat_session`` 归属到指定用户。

        **危险**：多用户环境下会把他人历史会话一并划给该用户，造成会话串用。
        已从 HTTP 列表接口移除自动调用；仅保留供单租户数据修复时在 Python 控制台等场景**显式**调用。
        """
        ts = utc_now_iso()
        return self._ui_session_owner_repo().backfill_orphan_sessions_for_user(
            tenant_id=str(tenant_id), user_id=str(user_id), default_created_at=ts
        )

    def get_session_for_user(self, *, session_id: str, tenant_id: str, user_id: str) -> Optional[ChatSession]:
        return self._chat_sessions_repo().fetch_chat_session_for_user(
            session_id=session_id, tenant_id=tenant_id, user_id=user_id
        )

    def list_sessions(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ChatSession]:
        return self._chat_sessions_repo().list_chat_sessions_global(limit=limit, offset=int(offset))

    def list_sessions_for_user(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ChatSession]:
        return self._chat_sessions_repo().list_chat_sessions_for_user(
            tenant_id=tenant_id,
            user_id=user_id,
            limit=limit,
            offset=int(offset),
        )

    def count_sessions(self) -> int:
        return self._chat_sessions_repo().count_chat_sessions_global()

    def get_sessions_list_meta(self) -> SessionsListMeta:
        return self._chat_sessions_repo().sessions_list_meta_global()

    def get_sessions_list_meta_for_user(self, *, tenant_id: str, user_id: str) -> SessionsListMeta:
        return self._chat_sessions_repo().sessions_list_meta_for_user(
            tenant_id=tenant_id, user_id=user_id
        )

    def list_sessions_for_administrator_username(
        self,
        *,
        username: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ChatSession]:
        return self._chat_sessions_repo().list_chat_sessions_for_administrator_username(
            username=username,
            limit=limit,
            offset=int(offset),
        )

    def get_sessions_list_meta_for_administrator_username(self, *, username: str) -> SessionsListMeta:
        return self._chat_sessions_repo().sessions_list_meta_for_administrator_username(
            username=username
        )

    def get_session_for_administrator_username(
        self, *, session_id: str, username: str
    ) -> Optional[ChatSession]:
        return self._chat_sessions_repo().fetch_chat_session_for_administrator_username(
            session_id=session_id,
            username=username,
        )

    def list_sessions_for_tenant(
        self,
        *,
        tenant_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ChatSession]:
        """All chat sessions that belong to ``tenant_id`` via ``ui_session_owner`` (any user)."""
        return self._chat_sessions_repo().list_chat_sessions_for_tenant(
            tenant_id=tenant_id, limit=limit, offset=int(offset)
        )

    def get_sessions_list_meta_for_tenant(self, *, tenant_id: str) -> SessionsListMeta:
        return self._chat_sessions_repo().sessions_list_meta_for_tenant(tenant_id=tenant_id)

    def get_session_in_tenant(self, *, session_id: str, tenant_id: str) -> Optional[ChatSession]:
        """Session exists and is linked to this tenant (``administrator`` global browse)."""
        return self._chat_sessions_repo().fetch_chat_session_in_tenant(
            session_id=session_id, tenant_id=tenant_id
        )

    @staticmethod
    def _attachments_contain_attachment_id(raw_attachments: Any, *, attachment_id: str) -> bool:
        aid = str(attachment_id or "").strip()
        if not aid:
            return False
        obj = raw_attachments
        if isinstance(raw_attachments, str):
            s = str(raw_attachments or "").strip()
            if not s:
                return False
            try:
                obj = json.loads(s)
            except Exception:
                return False
        if isinstance(obj, dict):
            items = [obj]
        elif isinstance(obj, list):
            items = obj
        else:
            return False
        for it in items:
            if not isinstance(it, dict):
                continue
            if str(it.get("attachment_id") or "").strip() == aid:
                return True
        return False

    def attachment_referenced_by_user(self, *, tenant_id: str, user_id: str, attachment_id: str, scan_limit: int = 2000) -> bool:
        aid = str(attachment_id or "").strip()
        tid = str(tenant_id or "").strip()
        uid = str(user_id or "").strip()
        if not aid or not tid or not uid:
            return False
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT m.attachments
                FROM chat_message m
                INNER JOIN ui_session_owner o ON o.session_id = m.session_id
                WHERE o.tenant_id = ? AND o.user_id = ? AND m.attachments IS NOT NULL AND m.attachments <> ''
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (tid, uid, int(max(1, scan_limit))),
            ).fetchall()
        for r in rows:
            if self._attachments_contain_attachment_id(r["attachments"], attachment_id=aid):
                return True
        return False

    def attachment_referenced_in_tenant(self, *, tenant_id: str, attachment_id: str, scan_limit: int = 4000) -> bool:
        aid = str(attachment_id or "").strip()
        tid = str(tenant_id or "").strip()
        if not aid or not tid:
            return False
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT m.attachments
                FROM chat_message m
                INNER JOIN ui_session_owner o ON o.session_id = m.session_id
                WHERE o.tenant_id = ? AND m.attachments IS NOT NULL AND m.attachments <> ''
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (tid, int(max(1, scan_limit))),
            ).fetchall()
        for r in rows:
            if self._attachments_contain_attachment_id(r["attachments"], attachment_id=aid):
                return True
        return False

    def link_attachment_acl(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
        attachment_id: str,
        source: str,
    ) -> None:
        tid = str(tenant_id or "").strip()
        uid = str(user_id or "").strip()
        sid = str(session_id or "").strip()
        aid = str(attachment_id or "").strip().lower()
        src = str(source or "").strip() or "unknown"
        if not tid or not uid or not sid or not aid:
            return
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO attachment_acl
                    (attachment_id, tenant_id, user_id, session_id, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (aid, tid, uid, sid, src, ts),
            )

    @staticmethod
    def _attachment_ids_for_acl_from_payload_items(items: list[dict[str, Any]]) -> list[str]:
        """Collect stable attachment ids from message attachment JSON (for ACL rows)."""
        out: list[str] = []
        seen: set[str] = set()
        ref_types = {"image_ref", "video_ref", "text_ref", "binary_ref"}
        relay_re = re.compile(r"^relay://attachments/[^/]+/([a-f0-9]{8,64})$", re.IGNORECASE)
        for a in items:
            if not isinstance(a, dict):
                continue
            typ = str(a.get("type") or "").strip().lower()
            aid = str(a.get("attachment_id") or a.get("attachmentId") or "").strip().lower()
            if typ in ref_types and aid:
                if aid not in seen:
                    seen.add(aid)
                    out.append(aid)
                continue
            if typ != "relay_pointer":
                continue
            if not aid:
                uri = str(a.get("pointer_uri") or "").strip()
                m = relay_re.match(uri)
                if m:
                    aid = str(m.group(1) or "").strip().lower()
            if aid and aid not in seen:
                seen.add(aid)
                out.append(aid)
        return out

    def sync_attachment_acl_from_chat_message_attachments(
        self,
        *,
        session_id: str,
        role: str,
        event_type: str | None,
        attachments: Any,
    ) -> None:
        """Best-effort: link chat_message attachments to session owner so strict ACL downloads work.

        Tool results already link in runtime; assistant rows (image specialist, inbound, etc.)
        historically did not, which breaks ``AIA_ATTACHMENT_ACL_STRICT=1``.
        """
        sid = str(session_id or "").strip()
        if not sid or attachments is None:
            return
        owner = self.get_ui_session_owner(session_id=sid) or {}
        tid = str(owner.get("tenant_id") or "").strip()
        uid = str(owner.get("user_id") or "").strip()
        if not tid or not uid:
            return
        items: list[dict[str, Any]] = []
        if isinstance(attachments, list):
            items = [x for x in attachments if isinstance(x, dict)]
        elif isinstance(attachments, dict):
            items = [attachments]
        else:
            return
        ids = self._attachment_ids_for_acl_from_payload_items(items)
        if not ids:
            return
        r = str(role or "").strip() or "-"
        ev = str(event_type or "").strip() or "-"
        src = f"chat_message:{r}:{ev}"[:240]
        for aid in ids:
            self.link_attachment_acl(
                tenant_id=tid,
                user_id=uid,
                session_id=sid,
                attachment_id=aid,
                source=src,
            )

    def attachment_acl_allows_user(self, *, tenant_id: str, user_id: str, attachment_id: str) -> bool:
        tid = str(tenant_id or "").strip()
        uid = str(user_id or "").strip()
        aid = str(attachment_id or "").strip().lower()
        if not tid or not uid or not aid:
            return False
        with self._connect() as conn:
            r = conn.execute(
                """
                SELECT 1
                FROM attachment_acl
                WHERE tenant_id = ? AND user_id = ? AND attachment_id = ?
                LIMIT 1
                """,
                (tid, uid, aid),
            ).fetchone()
        return bool(r)

    def attachment_acl_allows_tenant(self, *, tenant_id: str, attachment_id: str) -> bool:
        tid = str(tenant_id or "").strip()
        aid = str(attachment_id or "").strip().lower()
        if not tid or not aid:
            return False
        with self._connect() as conn:
            r = conn.execute(
                """
                SELECT 1
                FROM attachment_acl
                WHERE tenant_id = ? AND attachment_id = ?
                LIMIT 1
                """,
                (tid, aid),
            ).fetchone()
        return bool(r)

    def backfill_attachment_acl_from_messages(
        self,
        *,
        tenant_id: str,
        limit_messages: int = 50_000,
    ) -> dict[str, Any]:
        """Best-effort backfill: scan chat_message.attachments and populate attachment_acl.

        This is intended for one-off migration / operator maintenance.
        """
        tid = str(tenant_id or "").strip()
        lim = max(1, int(limit_messages))
        if not tid:
            return {"ok": False, "error": "tenant_id_required"}
        inserted = 0
        scanned_msgs = 0
        scanned_atts = 0
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT m.session_id, m.attachments, o.user_id
                FROM chat_message m
                INNER JOIN ui_session_owner o ON o.session_id = m.session_id
                WHERE o.tenant_id = ? AND m.attachments IS NOT NULL AND m.attachments <> ''
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (tid, lim),
            ).fetchall()
            ts = utc_now_iso()
            for r in rows:
                scanned_msgs += 1
                sid = str(r["session_id"] or "").strip()
                uid = str(r["user_id"] or "").strip()
                if not sid or not uid:
                    continue
                try:
                    obj = json.loads(str(r["attachments"] or ""))
                except Exception:
                    continue
                items = obj if isinstance(obj, list) else ([obj] if isinstance(obj, dict) else [])
                for a in items:
                    if not isinstance(a, dict):
                        continue
                    scanned_atts += 1
                    aid = str(a.get("attachment_id") or "").strip().lower()
                    if not aid:
                        continue
                    src = "backfill:chat_message"
                    cur = conn.execute(
                        """
                        INSERT OR IGNORE INTO attachment_acl
                            (attachment_id, tenant_id, user_id, session_id, source, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (aid, tid, uid, sid, src, ts),
                    )
                    inserted += int(cur.rowcount or 0)
        return {
            "ok": True,
            "tenant_id": tid,
            "scanned_messages": int(scanned_msgs),
            "scanned_attachments": int(scanned_atts),
            "inserted": int(inserted),
        }

    def list_admin_sessions(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        q: str | None = None,
        active_only: bool = False,
        active_window_minutes: int = 30,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[int, list[dict[str, Any]]]:
        tid = str(tenant_id or "").strip()
        if not tid:
            return 0, []
        uid = str(user_id or "").strip()
        q_text = str(q or "").strip().lower()
        win = max(1, int(active_window_minutes))
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=win)).isoformat()
        lim = max(1, min(int(limit), 500))
        off = max(0, int(offset))

        total, rows = self._chat_sessions_repo().list_admin_sessions(
            tenant_id=tid,
            user_id=uid or None,
            search_lower=q_text or None,
            active_only=active_only,
            active_cutoff_iso=cutoff,
            limit=lim,
            offset=off,
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            last_at = str(r["last_message_at"] or r["created_at"] or "")
            out.append(
                {
                    **r,
                    "is_active_30m": bool(last_at and last_at >= cutoff),
                }
            )
        return total, out

    def list_admin_user_stats(
        self,
        *,
        tenant_id: str,
        q: str | None = None,
        active_window_minutes: int = 30,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[int, list[dict[str, Any]], dict[str, Any]]:
        tid = str(tenant_id or "").strip()
        if not tid:
            return 0, [], {
                "total_tokens_est": 0,
                "active_sessions_30m": 0,
                "active_logins_30m": 0,
                "users_count": 0,
            }
        q_text = str(q or "").strip().lower()
        win = max(1, int(active_window_minutes))
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=win)).isoformat()
        lim = max(1, min(int(limit), 500))
        off = max(0, int(offset))

        pack = self._admin_user_stats_repo().fetch(
            tenant_id=tid,
            search_lower=q_text or None,
            cutoff_iso=cutoff,
            limit=lim,
            offset=off,
        )
        total_row_c = int(pack["total_users"] or 0)
        rows = pack["user_rows"]
        total_active_sessions = pack["total_active_sessions_30m"]
        total_active_logins = pack["total_active_logins_30m"]

        token_by_user: dict[str, int] = {}
        sessions_count_by_user: dict[str, int] = {}
        active_sessions_by_user: dict[str, int] = {}
        last_message_at_by_user: dict[str, str] = {}
        active_logins_by_user: dict[str, int] = {}
        last_seen_at_by_user: dict[str, str] = {}

        for tr in pack["trace_rows"]:
            uid = str(tr.get("user_id") or "")
            if not uid:
                continue
            try:
                payload = json.loads(tr.get("payload") or "{}")
            except Exception:
                payload = {}
            p = int(payload.get("prompt_tokens_est") or 0)
            r2 = int(payload.get("response_tokens_est") or 0)
            token_by_user[uid] = int(token_by_user.get(uid, 0)) + max(0, p) + max(0, r2)

        for sr in pack["sessions_count_rows"]:
            sessions_count_by_user[str(sr.get("user_id") or "")] = int(sr.get("c") or 0)

        for rr in pack["active_sess_rows"]:
            uid = str(rr.get("user_id") or "")
            active_sessions_by_user[uid] = int(rr.get("active_30m") or 0)
            last_message_at_by_user[uid] = str(rr.get("last_message_at") or "")

        for lr in pack["login_rows"]:
            uid = str(lr.get("user_id") or "")
            active_logins_by_user[uid] = int(lr.get("c") or 0)
            last_seen_at_by_user[uid] = str(lr.get("last_seen_at") or "")

        users: list[dict[str, Any]] = []
        for r in rows:
            uid = str(r["user_id"] or "")
            users.append(
                {
                    "user_id": uid,
                    "username": str(r["username"] or ""),
                    "display_name": str(r["display_name"] or ""),
                    "role": str(r["role"] or ""),
                    "is_active": bool(int(r["is_active"] or 0)),
                    "total_tokens_est": int(token_by_user.get(uid, 0)),
                    "sessions_count": int(sessions_count_by_user.get(uid, 0)),
                    "active_sessions_30m": int(active_sessions_by_user.get(uid, 0)),
                    "active_login_30m": int(active_logins_by_user.get(uid, 0)),
                    "last_message_at": str(last_message_at_by_user.get(uid, "")),
                    "last_seen_at": str(last_seen_at_by_user.get(uid, "")),
                }
            )

        totals = {
            "total_tokens_est": int(sum(int(x.get("total_tokens_est") or 0) for x in users)),
            "active_sessions_30m": int(total_active_sessions or 0),
            "active_logins_30m": int(total_active_logins or 0),
            "users_count": int(total_row_c or 0),
        }
        return int(total_row_c or 0), users, totals

    def delete_session_in_tenant(self, *, session_id: str, tenant_id: str) -> bool:
        """Delete session if it belongs to tenant."""
        return self._chat_sessions_repo().try_delete_chat_session_for_tenant(
            session_id=session_id, tenant_id=tenant_id
        )

    def delete_session_for_administrator_username(
        self, *, session_id: str, username: str
    ) -> bool:
        """Delete session owned by any ``app_user`` row with this login name (cross-tenant)."""
        return self._chat_sessions_repo().try_delete_chat_session_for_administrator_username(
            session_id=session_id, username=username
        )

    def delete_session(self, session_id: str) -> None:
        self._chat_sessions_repo().delete_chat_session_by_id(session_id=session_id)

    def delete_session_for_user(self, *, session_id: str, tenant_id: str, user_id: str) -> bool:
        return self._chat_sessions_repo().try_delete_chat_session_for_user(
            session_id=session_id, tenant_id=tenant_id, user_id=user_id
        )

    def delete_message(self, *, session_id: str, message_id: int) -> bool:
        return self._chat_messages_repo().delete_message_and_refresh_session(
            session_id=session_id, message_id=message_id
        )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Any | None = None,
        attachments: Any | None = None,
        turn_uuid: str | None = None,
        event_type: str | None = None,
        event_payload: Any | None = None,
        timestamp: str | None = None,
    ) -> ChatMessage:
        ts = timestamp or utc_now_iso()
        tool_calls_text = None
        if tool_calls is not None:
            if isinstance(tool_calls, str):
                tool_calls_text = tool_calls
            else:
                tool_calls_text = json.dumps(
                    scrub_nul_bytes_from_jsonable(tool_calls), ensure_ascii=False
                )
        attachments_text = None
        if attachments is not None:
            attachments_text = json.dumps(
                scrub_nul_bytes_from_jsonable(attachments), ensure_ascii=False
            )
        event_payload_text = None
        if event_payload is not None:
            if isinstance(event_payload, str):
                event_payload_text = event_payload
            else:
                event_payload_text = json.dumps(
                    scrub_nul_bytes_from_jsonable(event_payload), ensure_ascii=False, default=str
                )
        turn_uuid_text = str(turn_uuid or "").strip() or None
        event_type_text = str(event_type or "").strip() or None
        # PostgreSQL TEXT rejects NUL; SQLite accepts it — strip before SA insert.
        content_clean = str(scrub_nul_bytes_from_text(str(content)) or "")
        tool_calls_text = scrub_nul_bytes_from_text(tool_calls_text)
        attachments_text = scrub_nul_bytes_from_text(attachments_text)
        event_payload_text = scrub_nul_bytes_from_text(event_payload_text)
        turn_uuid_text = scrub_nul_bytes_from_text(turn_uuid_text)
        event_type_text = scrub_nul_bytes_from_text(event_type_text)
        if turn_uuid_text is not None and not str(turn_uuid_text).strip():
            turn_uuid_text = None
        if event_type_text is not None and not str(event_type_text).strip():
            event_type_text = None
        msg_id = self._chat_messages_repo().insert_message_and_touch_session(
            session_id=str(session_id if session_id is not None else ""),
            role=str(role),
            content=content_clean,
            tool_calls=tool_calls_text,
            attachments=attachments_text,
            turn_uuid=turn_uuid_text,
            event_type=event_type_text,
            event_payload=event_payload_text,
            timestamp=str(ts),
        )
        if _chat_message_persist_log_enabled():
            _LOG.warning(
                "chat_message_persisted backend=%s session_id=%s message_id=%s role=%s event_type=%s "
                "content_len=%d has_tool_calls=%s",
                "postgresql" if self._use_pg else "sqlite",
                str(session_id or "").strip(),
                int(msg_id),
                str(role),
                str(event_type_text or ""),
                len(str(content_clean or "")),
                bool(tool_calls_text),
            )
        try:
            self.sync_attachment_acl_from_chat_message_attachments(
                session_id=str(session_id or "").strip(),
                role=str(role or ""),
                event_type=str(event_type or "").strip() or None,
                attachments=attachments,
            )
        except Exception:
            pass
        return ChatMessage(
            id=msg_id,
            session_id=session_id,
            role=role,
            content=content_clean,
            tool_calls=tool_calls_text,
            attachments=attachments_text,
            turn_uuid=turn_uuid_text,
            event_type=event_type_text,
            event_payload=event_payload_text,
            timestamp=ts,
        )

    def update_message_content(
        self,
        *,
        session_id: str,
        message_id: int,
        content: str,
        event_payload: Any | None = None,
    ) -> bool:
        sid = str(session_id or "").strip()
        if not sid:
            return False
        mid = int(message_id or 0)
        if mid <= 0:
            return False
        event_payload_text = None
        if event_payload is not None:
            if isinstance(event_payload, str):
                event_payload_text = event_payload
            else:
                event_payload_text = json.dumps(
                    scrub_nul_bytes_from_jsonable(event_payload), ensure_ascii=False, default=str
                )
        event_payload_text = scrub_nul_bytes_from_text(event_payload_text)
        content_u = str(scrub_nul_bytes_from_text(str(content or "")) or "")
        return self._chat_messages_repo().update_message_content(
            session_id=sid,
            message_id=mid,
            content=content_u,
            event_payload_text=event_payload_text,
        )

    def get_messages(self, session_id: str, limit: int = 200) -> list[ChatMessage]:
        """返回最近 ``limit`` 条消息，顺序为时间正序（窗口内最早的一条在前）。"""
        if limit <= 0:
            return []
        sid = str(session_id or "").strip()
        if not sid:
            return []
        lim = max(1, min(int(limit), 2000))
        return self._chat_messages_repo().get_messages_recent_asc(session_id=sid, limit=lim)

    def get_messages_after_id(self, *, session_id: str, after_id: int, limit: int = 200) -> list[ChatMessage]:
        """Return messages with id > after_id in ASC order (bounded by limit)."""
        sid = str(session_id or "").strip()
        if not sid:
            return []
        aid = int(after_id or 0)
        lim = max(1, min(int(limit), 2000))
        return self._chat_messages_repo().get_messages_after_id(
            session_id=sid, after_id=aid, limit=lim
        )

    def add_tool_log(
        self,
        session_id: str,
        tool_name: str,
        args: dict[str, Any],
        result: Any,
        specialist: str | None = None,
        timestamp: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        ts = timestamp or utc_now_iso()
        raw_cap = str(self.get_setting("AIA_TOOL_LOG_MAX_CHARS") or "").strip()
        if not raw_cap:
            raw_cap = str(os.getenv("AIA_TOOL_LOG_MAX_CHARS") or "").strip()
        cap = 200_000
        if raw_cap.isdigit():
            cap = max(20_000, min(int(raw_cap), 2_000_000))
        args_capped = self._cap_json_for_log(args, max_chars=cap, keep_keys=())
        result_capped = self._cap_json_for_log(result, max_chars=cap, keep_keys=("ok", "error_code", "error"))
        self._tool_log_queries_repo().insert_tool_log(
            session_id=str(session_id),
            tool_name=str(tool_name),
            specialist=str(specialist or ""),
            args=json.dumps(args_capped, ensure_ascii=False, default=str),
            result=json.dumps(result_capped, ensure_ascii=False, default=str),
            timestamp=str(ts),
            duration_ms=duration_ms,
        )

    def get_tool_logs(self, session_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = self._tool_log_queries_repo().list_tool_logs_asc(
            session_id=str(session_id), limit=max(1, int(limit))
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "tool_name": r["tool_name"],
                    "specialist": str(r["specialist"] or ""),
                    "args": json.loads(r["args"]),
                    "result": json.loads(r["result"]),
                    "timestamp": r["timestamp"],
                    "duration_ms": r["duration_ms"],
                }
            )
        return out

    def list_session_tool_health(self, *, session_id: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
        lim = max(1, int(limit))
        sid = str(session_id or "").strip() or None
        raw = self._session_tool_health_repo().list_session_tool_health(session_id=sid, limit=lim)
        out: list[dict[str, Any]] = []
        for r in raw:
            tool_count = int(r["tool_count"] or 0)
            assistant_count = int(r["assistant_count"] or 0)
            unhealthy = assistant_count > 0 and tool_count == 0
            out.append(
                {
                    "session_id": str(r["session_id"] or ""),
                    "title": str(r["title"] or ""),
                    "last_message_at": str(r["last_message_at"] or ""),
                    "user_count": int(r["user_count"] or 0),
                    "assistant_count": assistant_count,
                    "tool_count": tool_count,
                    "mcp_tool_count": int(r["mcp_tool_count"] or 0),
                    "last_tool_at": str(r["last_tool_at"] or ""),
                    "status": "warn_no_tool_calls" if unhealthy else "ok",
                }
            )
        return out

    def move_tool_logs_to_session(self, *, from_session_id: str, to_session_id: str) -> int:
        src = str(from_session_id or "").strip()
        dst = str(to_session_id or "").strip()
        if not src or not dst or src == dst:
            return 0
        return self._tool_log_queries_repo().move_tool_logs_between_sessions(
            from_session_id=src, to_session_id=dst
        )

    def list_mcp_tool_usage_summary(self, *, limit: int = 200) -> list[dict[str, Any]]:
        rows = self._tool_log_queries_repo().list_mcp_tool_usage_summary(limit=max(1, int(limit)))
        out: list[dict[str, Any]] = []
        for r in rows:
            tool_name = str(r["tool_name"] or "")
            parts = tool_name.split("__", 2)
            server_id = parts[1] if len(parts) >= 3 else ""
            tool_short = parts[2] if len(parts) >= 3 else tool_name
            out.append(
                {
                    "tool_name": tool_name,
                    "server_id": server_id,
                    "mcp_tool_name": tool_short,
                    "specialist": str(r["specialist"] or ""),
                    "count": int(r["n"] or 0),
                    "last_ts": str(r["last_ts"] or ""),
                }
            )
        return out

    def list_mcp_tool_aggregate_usage(self) -> dict[str, dict[str, Any]]:
        """Cross-session counts and last call time per MCP tool name (``mcp__*``)."""
        rows = self._tool_log_queries_repo().list_mcp_tool_aggregate_usage()
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            tn = str(r["tool_name"] or "")
            if not tn:
                continue
            out[tn] = {"count": int(r["n"] or 0), "last_ts": str(r["last_ts"] or "")}
        return out

    def list_mcp_tool_call_logs(self, *, server_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        rows = self._tool_log_queries_repo().list_mcp_tool_call_logs(
            server_id=server_id, limit=max(1, int(limit))
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                args = json.loads(r["args"] or "{}")
            except Exception:
                args = {}
            try:
                result = json.loads(r["result"] or "{}")
            except Exception:
                result = {}
            tool_name = str(r["tool_name"] or "")
            parts = tool_name.split("__", 2)
            row_server_id = parts[1] if len(parts) >= 3 else ""
            row_tool_name = parts[2] if len(parts) >= 3 else tool_name
            out.append(
                {
                    "session_id": str(r["session_id"] or ""),
                    "tool_name": tool_name,
                    "server_id": row_server_id,
                    "mcp_tool_name": row_tool_name,
                    "specialist": str(r["specialist"] or ""),
                    "args": args,
                    "result": result,
                    "timestamp": str(r["timestamp"] or ""),
                    "duration_ms": int(r["duration_ms"] or 0),
                }
            )
        return out

    def delete_mcp_server(self, *, server_id: str) -> dict[str, int]:
        sid = str(server_id or "").strip()
        if not sid:
            return {"registry": 0, "tools": 0, "health": 0, "install_logs": 0}
        with self._connect() as conn:
            cur_tools = conn.execute("DELETE FROM mcp_server_tool WHERE server_id = ?", (sid,))
            cur_health = conn.execute("DELETE FROM mcp_server_health WHERE server_id = ?", (sid,))
            cur_logs = conn.execute("DELETE FROM mcp_server_installation WHERE server_id = ?", (sid,))
            cur_registry = conn.execute("DELETE FROM mcp_server_registry WHERE server_id = ?", (sid,))
        return {
            "registry": int(cur_registry.rowcount or 0),
            "tools": int(cur_tools.rowcount or 0),
            "health": int(cur_health.rowcount or 0),
            "install_logs": int(cur_logs.rowcount or 0),
        }

    def count_messages(self, session_id: str) -> int:
        return self._chat_messages_repo().count_messages(session_id=session_id)

    def get_session_messages_meta(self, session_id: str) -> SessionMessagesMeta:
        return self._chat_messages_repo().session_messages_meta(session_id=session_id)

    def get_last_message_id(self, session_id: str) -> int | None:
        return self._chat_messages_repo().last_message_id(session_id=session_id)

    def ensure_default_session(self) -> ChatSession:
        sessions = self.list_sessions(limit=1, offset=0)
        if sessions:
            return sessions[0]
        lang = (os.getenv("AIA_ASSISTANT_LANG") or "").strip().lower()
        title = "New Chat" if lang.startswith("en") else "新会话"
        return self.create_session(title)

    def rename_session(self, session_id: str, title: str) -> None:
        self._chat_sessions_repo().rename_chat_session(session_id=session_id, title=title)

    def trim_messages(self, session_id: str, keep_last: int) -> None:
        if keep_last <= 0:
            self.delete_session(session_id)
            return
        self._chat_messages_repo().trim_messages_keep_last(session_id=session_id, keep_last=keep_last)

    def fork_session(self, source_session_id: str, up_to_message_id: int, title: str) -> ChatSession:
        """将 `id <= up_to_message_id` 的消息复制到新会话，并重映射 tool 的 assistant_message_id。"""
        self._chat_messages_repo().fork_assert_anchor(
            source_session_id=source_session_id,
            up_to_message_id=up_to_message_id,
        )
        new_sess = self.create_session(title)
        self._chat_messages_repo().fork_copy_messages_to_session(
            source_session_id=source_session_id,
            up_to_message_id=up_to_message_id,
            new_session_id=new_sess.id,
        )
        return self.get_session(new_sess.id) or new_sess

    def set_setting(self, key: str, value: str) -> None:
        ts = utc_now_iso()
        self._app_settings_repo().upsert_plain(key=key, value=value, updated_at=ts)

    def get_setting(self, key: str) -> Optional[str]:
        row = self._app_settings_repo().fetch_row(key=key)
        if row is None:
            return None
        val, is_secret = row
        if is_secret != 0:
            return None
        return str(val)

    def set_secret(self, key: str, plain_text: str) -> None:
        ts = utc_now_iso()
        enc = _encode_secret(plain_text)
        self._app_settings_repo().upsert_secret(key=key, encoded_value=enc, updated_at=ts)

    def get_secret(self, key: str) -> Optional[str]:
        row = self._app_settings_repo().fetch_row(key=key)
        if row is None:
            return None
        val, is_secret = row
        if is_secret != 1:
            return None
        try:
            return _decode_secret(str(val))
        except Exception:
            return None

    def delete_setting(self, key: str) -> None:
        self._app_settings_repo().delete_key(key=key)

    def migrate_secrets_to_fernet(self) -> dict[str, int]:
        """Migrate legacy b64 secrets to a stronger scheme for both app settings and llm profiles.

        - On Windows: migrates to DPAPI when available.
        - On non-Windows: migrates to Fernet (requires AIA_ASSISTANT_MASTER_KEY + cryptography).

        This is safe to run multiple times.
        """
        if sys.platform != "win32" and _fernet() is None:
            raise _CryptoError("fernet is not available; set AIA_ASSISTANT_MASTER_KEY and install cryptography")

        ts = utc_now_iso()
        migrated_app_settings = self._app_settings_repo().migrate_b64_secrets(
            ts=ts,
            decode_secret=_decode_secret,
            encode_secret=_encode_secret,
            predicate_new_encoding=lambda enc: enc.startswith("fernet:") or enc.startswith("dpapi:"),
        )
        migrated_llm_profiles = 0
        with self._connect() as conn:
            profs = conn.execute(
                "SELECT id, api_key FROM llm_profile WHERE api_key IS NOT NULL AND api_key LIKE 'b64:%'"
            ).fetchall()
            for r in profs:
                pid = str(r["id"] or "")
                v = str(r["api_key"] or "")
                if not pid or not v:
                    continue
                try:
                    plain = _decode_secret(v)
                except Exception:
                    continue
                enc = _encode_secret(plain)
                if enc != v and (enc.startswith("fernet:") or enc.startswith("dpapi:")):
                    conn.execute(
                        "UPDATE llm_profile SET api_key = ?, updated_at = ? WHERE id = ?",
                        (enc, ts, pid),
                    )
                    migrated_llm_profiles += 1

        return {
            "migrated_app_settings": int(migrated_app_settings),
            "migrated_llm_profiles": int(migrated_llm_profiles),
        }

    def legacy_secret_stats(self) -> dict[str, Any]:
        """Return counts of legacy b64 secrets for UI warning."""
        legacy_b64_app = self._app_settings_repo().count_legacy_b64_secrets()
        with self._connect() as conn:
            row2 = conn.execute(
                "SELECT COUNT(1) AS n FROM llm_profile WHERE api_key IS NOT NULL AND api_key LIKE 'b64:%'"
            ).fetchone()
        return {
            "legacy_b64_app_settings": int(legacy_b64_app),
            "legacy_b64_llm_profiles": int((row2["n"] if row2 else 0) or 0),
        }

    def create_llm_profile(
        self,
        name: str,
        mode: str = "openai",
        model: str | None = None,
        base_url: str | None = None,
        *,
        owner_user_id: str | None = None,
    ) -> str:
        profile_id = uuid.uuid4().hex
        ts = utc_now_iso()
        own = str(owner_user_id).strip() if owner_user_id else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO llm_profile
                    (id, name, mode, model, base_url, api_key, updated_at, is_builtin, hide_in_ui, owner_user_id, thinking_mode_enabled, reasoning_effort)
                VALUES (?, ?, ?, ?, ?, NULL, ?, 0, 0, ?, 0, '')
                """,
                (profile_id, name, mode, model, base_url, ts, own),
            )
        return profile_id

    def list_llm_profiles(
        self,
        *,
        visible_only: bool = False,
        viewer_user_id: str | None = None,
        viewer_username: str | None = None,
        viewer_tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """无 viewer：全局池。administrator：全部 profile。其他用户：内置 + 本人 + 用户/租户级 grant。"""
        clauses: list[str] = []
        params: list[Any] = []
        if visible_only:
            clauses.append("COALESCE(hide_in_ui, 0) = 0")
        if viewer_user_id is None and viewer_username is None:
            clauses.append("(COALESCE(TRIM(owner_user_id), '') = '')")
        elif is_administrator_model_pool(viewer_username):
            pass
        elif viewer_user_id:
            tid = str(viewer_tenant_id or "").strip()
            if tid:
                clauses.append(
                    "(COALESCE(is_builtin, 0) = 1 OR TRIM(COALESCE(owner_user_id, '')) = ? "
                    "OR id IN (SELECT profile_id FROM llm_profile_user_grant "
                    "WHERE tenant_id = ? AND user_id = ?) "
                    "OR id IN (SELECT profile_id FROM llm_profile_tenant_grant WHERE tenant_id = ?))"
                )
                params.extend([str(viewer_user_id), tid, str(viewer_user_id), tid])
            else:
                clauses.append("(COALESCE(is_builtin, 0) = 1 OR owner_user_id = ?)")
                params.append(str(viewer_user_id))
        else:
            clauses.append("(COALESCE(TRIM(owner_user_id), '') = '')")
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
                SELECT id, name, mode, model, base_url, api_key, updated_at,
                       COALESCE(is_builtin, 0) AS is_builtin,
                       COALESCE(hide_in_ui, 0) AS hide_in_ui,
                       owner_user_id,
                       COALESCE(thinking_mode_enabled, 0) AS thinking_mode_enabled,
                       COALESCE(reasoning_effort, '') AS reasoning_effort
                FROM llm_profile
                {where_sql}
                ORDER BY COALESCE(is_builtin, 0) DESC, COALESCE(hide_in_ui, 0) ASC, updated_at DESC
                """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        uid = str(viewer_user_id or "").strip()
        is_admin = is_administrator_model_pool(viewer_username)
        no_viewer = viewer_user_id is None and viewer_username is None
        tid = str(viewer_tenant_id or "").strip()
        user_grant_ids: set[str] = set()
        tenant_grant_ids: set[str] = set()
        if uid and tid and not is_admin and not no_viewer:
            with self._connect() as conn:
                for gr in conn.execute(
                    "SELECT profile_id FROM llm_profile_user_grant WHERE tenant_id = ? AND user_id = ?",
                    (tid, uid),
                ).fetchall():
                    user_grant_ids.add(str(gr["profile_id"]))
                for gr in conn.execute(
                    "SELECT profile_id FROM llm_profile_tenant_grant WHERE tenant_id = ?",
                    (tid,),
                ).fetchall():
                    tenant_grant_ids.add(str(gr["profile_id"]))
        out: list[dict[str, Any]] = []
        for r in rows:
            own = str(r["owner_user_id"] or "").strip() if r["owner_user_id"] is not None else ""
            is_builtin = bool(int(r["is_builtin"] or 0))
            pid = str(r["id"])
            if no_viewer:
                mutable = True
                if is_builtin:
                    vis = "builtin"
                elif not own:
                    vis = "global"
                else:
                    vis = "owned"
            elif is_admin:
                mutable = True
                if is_builtin:
                    vis = "builtin"
                elif not own:
                    vis = "global"
                elif uid and own == uid:
                    vis = "owned"
                else:
                    vis = "other_user"
            elif is_builtin:
                mutable = True
                vis = "builtin"
            elif uid and own == uid:
                mutable = True
                vis = "owned"
            else:
                mutable = False
                if pid in user_grant_ids:
                    vis = "grant_user"
                else:
                    vis = "grant_tenant"
            out.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "mode": r["mode"],
                    "model": r["model"],
                    "base_url": r["base_url"],
                    "has_key": r["api_key"] is not None and str(r["api_key"]) != "",
                    "updated_at": r["updated_at"],
                    "is_builtin": is_builtin,
                    "hide_in_ui": bool(int(r["hide_in_ui"] or 0)),
                    "owner_user_id": own,
                    "thinking_mode_enabled": bool(int(r["thinking_mode_enabled"] or 0)),
                    "reasoning_effort": str(r["reasoning_effort"] or "").strip().lower(),
                    "mutable": mutable,
                    "visibility_reason": vis,
                }
            )
        return out

    def get_llm_profile(self, profile_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            r = conn.execute(
                """
                SELECT id, name, mode, model, base_url, api_key, updated_at,
                       COALESCE(is_builtin, 0) AS is_builtin,
                       COALESCE(hide_in_ui, 0) AS hide_in_ui,
                       owner_user_id,
                       COALESCE(thinking_mode_enabled, 0) AS thinking_mode_enabled,
                       COALESCE(reasoning_effort, '') AS reasoning_effort
                FROM llm_profile
                WHERE id = ?
                """,
                (profile_id,),
            ).fetchone()
        if not r:
            return None
        return {
            "id": r["id"],
            "name": r["name"],
            "mode": r["mode"],
            "model": r["model"],
            "base_url": r["base_url"],
            "has_key": r["api_key"] is not None and str(r["api_key"]) != "",
            "updated_at": r["updated_at"],
            "is_builtin": bool(int(r["is_builtin"] or 0)),
            "hide_in_ui": bool(int(r["hide_in_ui"] or 0)),
            "owner_user_id": str(r["owner_user_id"] or "").strip() if r["owner_user_id"] is not None else "",
            "thinking_mode_enabled": bool(int(r["thinking_mode_enabled"] or 0)),
            "reasoning_effort": str(r["reasoning_effort"] or "").strip().lower(),
        }

    def update_llm_profile(
        self,
        profile_id: str,
        name: str,
        mode: str,
        model: str | None,
        base_url: str | None,
        *,
        thinking_mode_enabled: bool | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        ts = utc_now_iso()
        think_val = None if thinking_mode_enabled is None else (1 if bool(thinking_mode_enabled) else 0)
        eff = None if reasoning_effort is None else str(reasoning_effort or "").strip().lower()
        if eff is not None and eff not in ("", "low", "medium", "high"):
            eff = ""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE llm_profile
                SET name = ?, mode = ?, model = ?, base_url = ?,
                    thinking_mode_enabled = COALESCE(?, thinking_mode_enabled),
                    reasoning_effort = COALESCE(?, reasoning_effort),
                    updated_at = ?
                WHERE id = ?
                """,
                (name, mode, model, base_url, think_val, eff, ts, profile_id),
            )

    def delete_llm_profile(self, profile_id: str) -> None:
        prof = self.get_llm_profile(profile_id)
        if prof and prof.get("is_builtin"):
            raise ValueError("cannot_delete_builtin_llm_profile")
        with self._connect() as conn:
            conn.execute("DELETE FROM llm_profile_user_grant WHERE profile_id = ?", (profile_id,))
            conn.execute("DELETE FROM llm_profile_tenant_grant WHERE profile_id = ?", (profile_id,))
            conn.execute("DELETE FROM llm_profile WHERE id = ?", (profile_id,))

    def grant_llm_profile_to_user(
        self,
        *,
        tenant_id: str,
        profile_id: str,
        user_id: str,
        created_by_user_id: str | None = None,
    ) -> str:
        tid = str(tenant_id or "").strip()
        pid = str(profile_id or "").strip()
        uid = str(user_id or "").strip()
        if not tid or not pid or not uid:
            raise ValueError("llm_grant_params_required")
        if not self.get_llm_profile(pid):
            raise ValueError("profile_not_found")
        if not self.get_user_by_id(tenant_id=tid, user_id=uid):
            raise ValueError("user_not_found")
        gid = uuid.uuid4().hex
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO llm_profile_user_grant
                    (id, tenant_id, profile_id, user_id, created_at, created_by_user_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (gid, tid, pid, uid, ts, str(created_by_user_id).strip() if created_by_user_id else None),
            )
            row = conn.execute(
                """
                SELECT id FROM llm_profile_user_grant
                WHERE tenant_id = ? AND profile_id = ? AND user_id = ?
                """,
                (tid, pid, uid),
            ).fetchone()
        if not row:
            raise ValueError("llm_grant_failed")
        return str(row["id"])

    def revoke_llm_profile_grant(self, *, tenant_id: str, profile_id: str, user_id: str) -> int:
        tid = str(tenant_id or "").strip()
        pid = str(profile_id or "").strip()
        uid = str(user_id or "").strip()
        if not tid or not pid or not uid:
            return 0
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM llm_profile_user_grant WHERE tenant_id = ? AND profile_id = ? AND user_id = ?",
                (tid, pid, uid),
            )
        return int(cur.rowcount or 0)

    def list_llm_profile_grants_for_profile(self, tenant_id: str, profile_id: str) -> list[dict[str, Any]]:
        tid = str(tenant_id or "").strip()
        pid = str(profile_id or "").strip()
        if not tid or not pid:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT g.id AS grant_id, g.user_id, g.created_at, g.created_by_user_id,
                       u.username AS user_username, u.display_name AS user_display_name
                FROM llm_profile_user_grant g
                LEFT JOIN app_user u ON u.id = g.user_id AND u.tenant_id = g.tenant_id
                WHERE g.tenant_id = ? AND g.profile_id = ?
                ORDER BY g.created_at DESC
                """,
                (tid, pid),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "grant_id": r["grant_id"],
                    "user_id": r["user_id"],
                    "created_at": r["created_at"],
                    "created_by_user_id": r["created_by_user_id"] or "",
                    "username": str(r["user_username"] or "").strip(),
                    "display_name": str(r["user_display_name"] or "").strip(),
                }
            )
        return out

    def user_has_llm_profile_grant(self, tenant_id: str, user_id: str, profile_id: str) -> bool:
        tid = str(tenant_id or "").strip()
        uid = str(user_id or "").strip()
        pid = str(profile_id or "").strip()
        if not tid or not uid or not pid:
            return False
        with self._connect() as conn:
            n = conn.execute(
                """
                SELECT 1 FROM llm_profile_user_grant
                WHERE tenant_id = ? AND user_id = ? AND profile_id = ?
                LIMIT 1
                """,
                (tid, uid, pid),
            ).fetchone()
        return n is not None

    def grant_llm_profile_to_tenant(
        self,
        *,
        tenant_id: str,
        profile_id: str,
        created_by_user_id: str | None = None,
    ) -> str:
        tid = str(tenant_id or "").strip()
        pid = str(profile_id or "").strip()
        if not tid or not pid:
            raise ValueError("llm_grant_params_required")
        if not self.get_llm_profile(pid):
            raise ValueError("profile_not_found")
        gid = uuid.uuid4().hex
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO llm_profile_tenant_grant
                    (id, tenant_id, profile_id, created_at, created_by_user_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (gid, tid, pid, ts, str(created_by_user_id).strip() if created_by_user_id else None),
            )
            row = conn.execute(
                "SELECT id FROM llm_profile_tenant_grant WHERE tenant_id = ? AND profile_id = ?",
                (tid, pid),
            ).fetchone()
        if not row:
            raise ValueError("llm_grant_failed")
        return str(row["id"])

    def revoke_llm_profile_tenant_grant(self, *, tenant_id: str, profile_id: str) -> int:
        tid = str(tenant_id or "").strip()
        pid = str(profile_id or "").strip()
        if not tid or not pid:
            return 0
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM llm_profile_tenant_grant WHERE tenant_id = ? AND profile_id = ?",
                (tid, pid),
            )
        return int(cur.rowcount or 0)

    def tenant_has_llm_profile_grant(self, tenant_id: str, profile_id: str) -> bool:
        tid = str(tenant_id or "").strip()
        pid = str(profile_id or "").strip()
        if not tid or not pid:
            return False
        with self._connect() as conn:
            n = conn.execute(
                """
                SELECT 1 FROM llm_profile_tenant_grant
                WHERE tenant_id = ? AND profile_id = ?
                LIMIT 1
                """,
                (tid, pid),
            ).fetchone()
        return n is not None

    def ensure_personal_llm_clone_from_global(self, user_id: str, username: str | None) -> None:
        """非 administrator：首次进入模型页/对话前，把全局池中的自定义 profile 复制一份并挂上独立 active/bindings。"""
        if is_administrator_model_pool(username):
            return
        uid = str(user_id or "").strip()
        if not uid:
            return
        from runtime.agents.specialists import dump_agent_profile_bindings, parse_agent_profile_bindings

        seeded_key = f"llm_personal_pool_seeded:{uid}"
        act_key = active_llm_profile_setting_key(uid, username)
        bind_key = agent_profile_bindings_setting_key(uid, username)
        ts = utc_now_iso()

        def _get_setting_conn(conn: sqlite3.Connection, key: str) -> str | None:
            row = conn.execute(
                "SELECT value, is_secret FROM app_setting WHERE key = ?",
                (key,),
            ).fetchone()
            if not row or int(row["is_secret"] or 0) != 0:
                return None
            return str(row["value"])

        def _upsert_setting_conn(conn: sqlite3.Connection, key: str, value: str) -> None:
            conn.execute(
                """
                INSERT INTO app_setting (key, value, is_secret, updated_at)
                VALUES (?, ?, 0, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, is_secret = 0, updated_at = excluded.updated_at
                """,
                (key, value, ts),
            )

        with self._connect() as conn:
            if str(_get_setting_conn(conn, seeded_key) or "").strip() == "1":
                return
            own_n = conn.execute(
                """
                SELECT COUNT(*) AS c FROM llm_profile
                WHERE owner_user_id = ? AND COALESCE(is_builtin, 0) = 0
                """,
                (uid,),
            ).fetchone()["c"]
            if int(own_n or 0) > 0:
                _upsert_setting_conn(conn, seeded_key, "1")
                return
            rows = conn.execute(
                """
                SELECT id, name, mode, model, base_url, api_key, hide_in_ui
                FROM llm_profile
                WHERE (owner_user_id IS NULL OR TRIM(owner_user_id) = '')
                  AND COALESCE(is_builtin, 0) = 0
                """,
            ).fetchall()
            id_map: dict[str, str] = {}
            for r in rows:
                old_id = str(r["id"])
                new_id = uuid.uuid4().hex
                id_map[old_id] = new_id
                conn.execute(
                    """
                    INSERT INTO llm_profile
                        (id, name, mode, model, base_url, api_key, updated_at, is_builtin, hide_in_ui, owner_user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        new_id,
                        r["name"],
                        r["mode"],
                        r["model"],
                        r["base_url"],
                        r["api_key"],
                        ts,
                        int(r["hide_in_ui"] or 0),
                        uid,
                    ),
                )
            global_active = str(_get_setting_conn(conn, "active_llm_profile_id") or "").strip()
            if global_active:
                if global_active in id_map:
                    _upsert_setting_conn(conn, act_key, id_map[global_active])
                else:
                    _upsert_setting_conn(conn, act_key, global_active)
            else:
                _upsert_setting_conn(conn, act_key, LLM_BUILTIN_OLLAMA_PROFILE_ID)
            raw_g = _get_setting_conn(conn, _MODEL_BINDINGS_KEY)
            parsed = parse_agent_profile_bindings(raw_g)
            for rid in list(parsed.keys()):
                v = str(parsed.get(rid) or "").strip()
                if v in id_map:
                    parsed[rid] = id_map[v]
            _upsert_setting_conn(conn, bind_key, dump_agent_profile_bindings(parsed))
            _upsert_setting_conn(conn, seeded_key, "1")

    def set_llm_profile_secret(self, profile_id: str, plain_text: str) -> None:
        ts = utc_now_iso()
        enc = _encode_secret(plain_text)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE llm_profile
                SET api_key = ?, updated_at = ?
                WHERE id = ?
                """,
                (enc, ts, profile_id),
            )

    def clear_llm_profile_secret(self, profile_id: str) -> None:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE llm_profile
                SET api_key = NULL, updated_at = ?
                WHERE id = ?
                """,
                (ts, profile_id),
            )

    def get_llm_profile_secret(self, profile_id: str) -> Optional[str]:
        with self._connect() as conn:
            r = conn.execute(
                "SELECT api_key FROM llm_profile WHERE id = ?",
                (profile_id,),
            ).fetchone()
        if not r:
            return None
        val = r["api_key"]
        if val is None or str(val) == "":
            return None
        try:
            return _decode_secret(str(val))
        except Exception:
            return None

    def upsert_knowledge_chunk(
        self,
        *,
        chunk_id: str,
        source: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_chunk (chunk_id, source, content, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    source = excluded.source,
                    content = excluded.content,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at
                """,
                (
                    chunk_id,
                    source,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False, default=str),
                    ts,
                ),
            )

    def search_knowledge(self, *, query: str, limit: int = 3) -> list[dict[str, Any]]:
        token = (query or "").strip()
        if not token:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source, content, metadata, updated_at
                FROM knowledge_chunk
                WHERE content LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (f"%{token[:64]}%", max(1, int(limit))),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                meta = json.loads(r["metadata"])
            except (json.JSONDecodeError, TypeError):
                meta = {}
            out.append(
                {
                    "source": r["source"],
                    "content": r["content"],
                    "metadata": meta,
                    "updated_at": r["updated_at"],
                }
            )
        return out

    def get_knowledge_chunks(self, *, chunk_ids: list[str]) -> list[dict[str, Any]]:
        ids = [str(x) for x in (chunk_ids or []) if str(x)]
        if not ids:
            return []
        # SQLite parameter limit is high enough for our small uses; still cap.
        ids = ids[:500]
        qmarks = ",".join(["?"] * len(ids))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT chunk_id, source, content, metadata, updated_at
                FROM knowledge_chunk
                WHERE chunk_id IN ({qmarks})
                """,
                tuple(ids),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                meta = json.loads(r["metadata"])
            except Exception:
                meta = {}
            out.append(
                {
                    "chunk_id": r["chunk_id"],
                    "source": r["source"],
                    "content": r["content"],
                    "metadata": meta,
                    "updated_at": r["updated_at"],
                }
            )
        return out

    def upsert_knowledge_embedding(
        self,
        *,
        chunk_id: str,
        model: str,
        vector: list[float],
    ) -> None:
        ts = utc_now_iso()
        vec = [float(x) for x in (vector or [])]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_embedding (chunk_id, model, dim, vector_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id, model) DO UPDATE SET
                    dim = excluded.dim,
                    vector_json = excluded.vector_json,
                    updated_at = excluded.updated_at
                """,
                (str(chunk_id), str(model), int(len(vec)), json.dumps(vec), ts),
            )

    def ensure_memory_tables(self) -> None:
        # tables are initialized in _init_db; this method is used by callers
        # that need an explicit bootstrap hook.
        with self._connect() as conn:
            conn.execute("SELECT 1 FROM memory_item LIMIT 1")

    def upsert_memory_item(
        self,
        *,
        memory_id: str,
        tenant_id: str,
        user_id: str,
        session_id: str,
        memory_type: str,
        content: str,
        confidence: float,
        source: str,
        metadata: dict[str, Any] | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
        expires_at: str | None = None,
    ) -> None:
        self.ensure_memory_tables()
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_item
                    (memory_id, tenant_id, user_id, session_id, memory_type, content, confidence, source, metadata, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    user_id = excluded.user_id,
                    session_id = excluded.session_id,
                    memory_type = excluded.memory_type,
                    content = excluded.content,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
                """,
                (
                    str(memory_id),
                    str(tenant_id),
                    str(user_id),
                    str(session_id),
                    str(memory_type),
                    str(content or ""),
                    float(confidence),
                    str(source or "memory"),
                    json.dumps(metadata or {}, ensure_ascii=False, default=str),
                    str(created_at or ts),
                    str(updated_at or ts),
                    str(expires_at) if expires_at else None,
                ),
            )

    def upsert_memory_vector(
        self,
        *,
        memory_id: str,
        model: str,
        vector: list[float],
        updated_at: str | None = None,
    ) -> None:
        self.ensure_memory_tables()
        ts = updated_at or utc_now_iso()
        vec = [float(x) for x in (vector or [])]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_vector (memory_id, model, dim, vector_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(memory_id, model) DO UPDATE SET
                    dim = excluded.dim,
                    vector_json = excluded.vector_json,
                    updated_at = excluded.updated_at
                """,
                (str(memory_id), str(model), len(vec), json.dumps(vec), ts),
            )

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        n = min(len(a), len(b))
        if n <= 0:
            return 0.0
        dot = 0.0
        na = 0.0
        nb = 0.0
        for i in range(n):
            x = float(a[i])
            y = float(b[i])
            dot += x * y
            na += x * x
            nb += y * y
        if na <= 1e-9 or nb <= 1e-9:
            return 0.0
        return float(dot / ((na**0.5) * (nb**0.5)))

    def search_memory_vectors(
        self,
        *,
        query_vector: list[float],
        model: str,
        tenant_id: str,
        user_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        self.ensure_memory_tables()
        lim = max(1, min(int(limit), 100))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT mi.memory_id, mi.tenant_id, mi.user_id, mi.session_id, mi.memory_type,
                       mi.content, mi.confidence, mi.source, mi.metadata, mi.created_at, mi.updated_at, mi.expires_at,
                       mv.vector_json
                FROM memory_item mi
                JOIN memory_vector mv ON mv.memory_id = mi.memory_id
                WHERE mv.model = ? AND mi.tenant_id = ? AND mi.user_id = ?
                  AND (mi.expires_at IS NULL OR mi.expires_at > ?)
                ORDER BY mi.updated_at DESC
                LIMIT 5000
                """,
                (str(model), str(tenant_id), str(user_id), utc_now_iso()),
            ).fetchall()
        scored: list[tuple[float, dict[str, Any]]] = []
        q = [float(x) for x in (query_vector or [])]
        for r in rows:
            try:
                vec = json.loads(r["vector_json"])
            except Exception:
                continue
            score = self._cosine_similarity(q, [float(x) for x in (vec or [])])
            try:
                meta = json.loads(r["metadata"])
            except Exception:
                meta = {}
            scored.append(
                (
                    score,
                    {
                        "memory_id": r["memory_id"],
                        "tenant_id": r["tenant_id"],
                        "user_id": r["user_id"],
                        "session_id": r["session_id"],
                        "memory_type": r["memory_type"],
                        "content": r["content"],
                        "confidence": float(r["confidence"] or 0.0),
                        "source": r["source"],
                        "metadata": meta,
                        "created_at": r["created_at"],
                        "updated_at": r["updated_at"],
                        "expires_at": r["expires_at"],
                        "score": float(score),
                    },
                )
            )
        scored.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in scored[:lim]]

    def list_memory_items(
        self,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        self.ensure_memory_tables()
        where: list[str] = []
        params: list[Any] = []
        if tenant_id:
            where.append("tenant_id = ?")
            params.append(str(tenant_id))
        if user_id:
            where.append("user_id = ?")
            params.append(str(user_id))
        wsql = ("WHERE " + " AND ".join(where)) if where else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT memory_id, tenant_id, user_id, session_id, memory_type, content, confidence, source, metadata, created_at, updated_at, expires_at
                FROM memory_item
                {wsql}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (*params, max(1, min(int(limit), 500)), max(0, int(offset))),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                meta = json.loads(r["metadata"])
            except Exception:
                meta = {}
            out.append(
                {
                    "memory_id": r["memory_id"],
                    "tenant_id": r["tenant_id"],
                    "user_id": r["user_id"],
                    "session_id": r["session_id"],
                    "memory_type": r["memory_type"],
                    "content": r["content"],
                    "confidence": float(r["confidence"] or 0.0),
                    "source": r["source"],
                    "metadata": meta,
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "expires_at": r["expires_at"],
                }
            )
        return out

    def delete_memory_item(self, *, memory_id: str) -> int:
        self.ensure_memory_tables()
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM memory_item WHERE memory_id = ?", (str(memory_id),))
        return int(cur.rowcount or 0)

    def add_memory_hit_log(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str | None,
        memory_id: str | None,
        query_text: str,
        score: float,
        source: str,
        timestamp: str | None = None,
    ) -> None:
        self.ensure_memory_tables()
        ts = timestamp or utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_hit_log (tenant_id, user_id, session_id, memory_id, query_text, score, source, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(tenant_id),
                    str(user_id),
                    str(session_id) if session_id else None,
                    str(memory_id) if memory_id else None,
                    str(query_text or ""),
                    float(score),
                    str(source or "memory"),
                    ts,
                ),
            )

    def list_memory_hit_logs(
        self,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self.ensure_memory_tables()
        where: list[str] = []
        params: list[Any] = []
        if tenant_id:
            where.append("tenant_id = ?")
            params.append(str(tenant_id))
        if user_id:
            where.append("user_id = ?")
            params.append(str(user_id))
        wsql = ("WHERE " + " AND ".join(where)) if where else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, tenant_id, user_id, session_id, memory_id, query_text, score, source, timestamp
                FROM memory_hit_log
                {wsql}
                ORDER BY id DESC
                LIMIT ?
                """,
                (*params, max(1, min(int(limit), 500))),
            ).fetchall()
        return [
            {
                "id": int(r["id"]),
                "tenant_id": r["tenant_id"],
                "user_id": r["user_id"],
                "session_id": r["session_id"],
                "memory_id": r["memory_id"],
                "query_text": r["query_text"],
                "score": float(r["score"] or 0.0),
                "source": r["source"],
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]

    def clear_low_confidence_memory(self, *, max_confidence: float) -> int:
        self.ensure_memory_tables()
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM memory_item WHERE confidence <= ?", (float(max_confidence),))
        return int(cur.rowcount or 0)

    def list_knowledge_embeddings(self, *, model: str, limit: int = 5000) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, model, dim, vector_json, updated_at
                FROM knowledge_embedding
                WHERE model = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (str(model), max(1, int(limit))),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                vec = json.loads(r["vector_json"])
            except Exception:
                vec = []
            out.append(
                {
                    "chunk_id": r["chunk_id"],
                    "model": r["model"],
                    "dim": int(r["dim"] or 0),
                    "vector": vec,
                    "updated_at": r["updated_at"],
                }
            )
        return out

    def add_agent_audit_log(
        self,
        *,
        session_id: str,
        specialist: str,
        task_kind: str,
        action: str,
        payload: dict[str, Any],
        status: str,
        reason: str,
        duration_ms: int = 0,
    ) -> None:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_audit_log
                    (session_id, specialist, task_kind, action, payload, status, reason, duration_ms, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    specialist,
                    task_kind,
                    action,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    status,
                    reason,
                    int(duration_ms),
                    ts,
                ),
            )

    def add_agent_eval_log(
        self,
        *,
        session_id: str,
        specialist: str,
        task_kind: str,
        success: bool,
        latency_ms: int,
        cost_hint: float = 0.0,
        notes: str = "",
    ) -> None:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_eval_log
                    (session_id, specialist, task_kind, success, latency_ms, cost_hint, notes, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    specialist,
                    task_kind,
                    1 if success else 0,
                    int(latency_ms),
                    float(cost_hint),
                    notes,
                    ts,
                ),
            )

    def list_agent_eval_logs(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id, specialist, task_kind, success, latency_ms, cost_hint, notes, timestamp
                FROM agent_eval_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [
            {
                "session_id": r["session_id"],
                "specialist": r["specialist"],
                "task_kind": r["task_kind"],
                "success": bool(int(r["success"] or 0)),
                "latency_ms": int(r["latency_ms"] or 0),
                "cost_hint": float(r["cost_hint"] or 0.0),
                "notes": r["notes"],
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]

    def list_agent_audit_logs(
        self,
        *,
        limit: int = 200,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    """
                    SELECT session_id, specialist, task_kind, action, payload, status, reason, duration_ms, timestamp
                    FROM agent_audit_log
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (str(session_id), max(1, int(limit))),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT session_id, specialist, task_kind, action, payload, status, reason, duration_ms, timestamp
                    FROM agent_audit_log
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (max(1, int(limit)),),
                ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                payload = json.loads(r["payload"])
            except (json.JSONDecodeError, TypeError):
                payload = {}
            out.append(
                {
                    "session_id": r["session_id"],
                    "specialist": r["specialist"],
                    "task_kind": r["task_kind"],
                    "action": r["action"],
                    "payload": payload,
                    "status": r["status"],
                    "reason": r["reason"],
                    "duration_ms": int(r["duration_ms"] or 0),
                    "timestamp": r["timestamp"],
                }
            )
        return out

    def upsert_tool_plugin(
        self,
        *,
        plugin_name: str,
        plugin_version: str,
        entry_point: str,
        enabled: bool = True,
    ) -> None:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tool_plugin (plugin_name, plugin_version, entry_point, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(plugin_name, entry_point) DO UPDATE SET
                    plugin_version = excluded.plugin_version,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (str(plugin_name), str(plugin_version), str(entry_point), 1 if enabled else 0, ts),
            )

    def list_tool_plugins(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT plugin_name, plugin_version, entry_point, enabled, updated_at
                FROM tool_plugin
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [
            {
                "plugin_name": r["plugin_name"],
                "plugin_version": r["plugin_version"],
                "entry_point": r["entry_point"],
                "enabled": bool(int(r["enabled"] or 0)),
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def upsert_mcp_server(
        self,
        *,
        server_id: str,
        source_type: str,
        source_ref: str,
        version: str = "",
        entry_command: str = "",
        entry_args: list[str] | None = None,
        env_schema: dict[str, Any] | None = None,
        required_permissions: list[str] | None = None,
        risk_level: str = "high",
        timeout_s: float = 30.0,
        enabled: bool = False,
    ) -> None:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mcp_server_registry
                    (server_id, source_type, source_ref, version, entry_command, entry_args, env_schema,
                     required_permissions, risk_level, timeout_s, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(server_id) DO UPDATE SET
                    source_type = excluded.source_type,
                    source_ref = excluded.source_ref,
                    version = excluded.version,
                    entry_command = excluded.entry_command,
                    entry_args = excluded.entry_args,
                    env_schema = excluded.env_schema,
                    required_permissions = excluded.required_permissions,
                    risk_level = excluded.risk_level,
                    timeout_s = excluded.timeout_s,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    str(server_id),
                    str(source_type),
                    str(source_ref),
                    str(version or ""),
                    str(entry_command or ""),
                    json.dumps(entry_args or [], ensure_ascii=False),
                    json.dumps(env_schema or {}, ensure_ascii=False),
                    json.dumps(required_permissions or [], ensure_ascii=False),
                    str(risk_level or "high"),
                    float(timeout_s or 30.0),
                    1 if enabled else 0,
                    ts,
                ),
            )

    def set_mcp_server_enabled(self, *, server_id: str, enabled: bool) -> int:
        ts = utc_now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE mcp_server_registry SET enabled = ?, updated_at = ? WHERE server_id = ?",
                (1 if enabled else 0, ts, str(server_id)),
            )
        return int(cur.rowcount or 0)

    def list_mcp_servers(self, *, enabled_only: bool = False) -> list[dict[str, Any]]:
        sql = """
            SELECT server_id, source_type, source_ref, version, entry_command, entry_args, env_schema,
                   required_permissions, risk_level, timeout_s, enabled, updated_at
            FROM mcp_server_registry
        """
        params: tuple[Any, ...] = ()
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                entry_args = json.loads(r["entry_args"] or "[]")
            except Exception:
                entry_args = []
            try:
                env_schema = json.loads(r["env_schema"] or "{}")
            except Exception:
                env_schema = {}
            try:
                required_permissions = json.loads(r["required_permissions"] or "[]")
            except Exception:
                required_permissions = []
            out.append(
                {
                    "server_id": r["server_id"],
                    "source_type": r["source_type"],
                    "source_ref": r["source_ref"],
                    "version": r["version"],
                    "entry_command": r["entry_command"],
                    "entry_args": entry_args if isinstance(entry_args, list) else [],
                    "env_schema": env_schema if isinstance(env_schema, dict) else {},
                    "required_permissions": required_permissions if isinstance(required_permissions, list) else [],
                    "risk_level": r["risk_level"],
                    "timeout_s": float(r["timeout_s"] or 30.0),
                    "enabled": bool(int(r["enabled"] or 0)),
                    "updated_at": r["updated_at"],
                }
            )
        return out

    def add_mcp_installation_log(
        self,
        *,
        server_id: str,
        status: str,
        error_code: str = "",
        detail: dict[str, Any] | None = None,
        install_command: str = "",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mcp_server_installation
                    (server_id, status, error_code, detail, install_command, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(server_id),
                    str(status),
                    str(error_code or ""),
                    json.dumps(detail or {}, ensure_ascii=False),
                    str(install_command or ""),
                    utc_now_iso(),
                ),
            )

    def list_mcp_installation_logs(self, *, server_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        where = ""
        params: list[Any] = []
        if server_id:
            where = "WHERE server_id = ?"
            params.append(str(server_id))
        params.append(max(1, int(limit)))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT server_id, status, error_code, detail, install_command, timestamp
                FROM mcp_server_installation
                {where}
                ORDER BY id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                detail = json.loads(r["detail"] or "{}")
            except Exception:
                detail = {}
            out.append(
                {
                    "server_id": r["server_id"],
                    "status": r["status"],
                    "error_code": r["error_code"],
                    "detail": detail,
                    "install_command": r["install_command"],
                    "timestamp": r["timestamp"],
                }
            )
        return out

    def list_mcp_install_failure_summary(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT server_id, error_code, COUNT(1) AS n, MAX(timestamp) AS last_ts
                FROM mcp_server_installation
                WHERE status = 'error'
                GROUP BY server_id, error_code
                ORDER BY n DESC, last_ts DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [
            {
                "server_id": str(r["server_id"] or ""),
                "error_code": str(r["error_code"] or ""),
                "count": int(r["n"] or 0),
                "last_ts": str(r["last_ts"] or ""),
            }
            for r in rows
        ]

    def set_mcp_server_health(self, *, server_id: str, status: str, detail: dict[str, Any] | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mcp_server_health (server_id, status, detail, checked_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(server_id) DO UPDATE SET
                    status = excluded.status,
                    detail = excluded.detail,
                    checked_at = excluded.checked_at
                """,
                (str(server_id), str(status), json.dumps(detail or {}, ensure_ascii=False), utc_now_iso()),
            )

    def list_mcp_server_health(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT server_id, status, detail, checked_at FROM mcp_server_health ORDER BY checked_at DESC"
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                detail = json.loads(r["detail"] or "{}")
            except Exception:
                detail = {}
            out.append(
                {"server_id": r["server_id"], "status": r["status"], "detail": detail, "checked_at": r["checked_at"]}
            )
        return out

    def replace_mcp_server_tools(self, *, server_id: str, tools: list[dict[str, Any]]) -> None:
        ts = utc_now_iso()
        sid = str(server_id or "").strip()
        if not sid:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM mcp_server_tool WHERE server_id = ?", (sid,))
            for t in tools:
                tool_name = str((t or {}).get("tool_name") or "").strip()
                if not tool_name:
                    continue
                conn.execute(
                    """
                    INSERT INTO mcp_server_tool (server_id, tool_name, description, parameters, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        sid,
                        tool_name,
                        str((t or {}).get("description") or ""),
                        json.dumps((t or {}).get("parameters") or {}, ensure_ascii=False),
                        ts,
                    ),
                )

    def list_mcp_server_tools(self, *, server_id: str) -> list[dict[str, Any]]:
        sid = str(server_id or "").strip()
        if not sid:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT tool_name, description, parameters, updated_at
                FROM mcp_server_tool
                WHERE server_id = ?
                ORDER BY tool_name ASC
                """,
                (sid,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                parameters = json.loads(r["parameters"] or "{}")
            except Exception:
                parameters = {}
            out.append(
                {
                    "tool_name": r["tool_name"],
                    "description": r["description"],
                    "parameters": parameters if isinstance(parameters, dict) else {},
                    "updated_at": r["updated_at"],
                }
            )
        return out

    def add_trace_event(
        self,
        *,
        session_id: str,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        ts = utc_now_iso()
        self._trace_events_repo().insert_one(
            session_id=str(session_id),
            trace_id=str(trace_id),
            span_id=str(span_id),
            parent_span_id=str(parent_span_id) if parent_span_id else None,
            event_type=str(event_type),
            payload=json.dumps(payload or {}, ensure_ascii=False, default=str),
            timestamp=ts,
        )

    def add_trace_events_batch(self, events: list[dict[str, Any]]) -> None:
        ts = utc_now_iso()
        batch: list[dict[str, Any]] = []
        for e in events or []:
            try:
                session_id = str(e.get("session_id") or "").strip()
                trace_id = str(e.get("trace_id") or "").strip()
                span_id = str(e.get("span_id") or "").strip()
                if (not session_id) or (not trace_id) or (not span_id):
                    continue
                parent_span_id = str(e.get("parent_span_id") or "").strip() or None
                event_type = str(e.get("event_type") or "").strip()
                payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
                batch.append(
                    {
                        "session_id": session_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id,
                        "event_type": event_type,
                        "payload": json.dumps(payload or {}, ensure_ascii=False, default=str),
                        "timestamp": ts,
                    }
                )
            except Exception:
                continue
        self._trace_events_repo().insert_many(batch)

    def list_trace_events(self, *, session_id: str, limit: int = 300) -> list[dict[str, Any]]:
        rows = self._trace_events_repo().list_trace_events_desc(
            session_id=str(session_id), limit=max(1, int(limit))
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                payload = json.loads(r["payload"])
            except Exception:
                payload = {}
            out.append(
                {
                    "trace_id": r["trace_id"],
                    "span_id": r["span_id"],
                    "parent_span_id": r["parent_span_id"],
                    "event_type": r["event_type"],
                    "payload": payload,
                    "timestamp": r["timestamp"],
                }
            )
        return out

    def list_trace_events_for_trace(
        self, *, session_id: str, trace_id: str, limit: int = 500
    ) -> list[dict[str, Any]]:
        rows = self._trace_events_repo().list_trace_events_for_trace_asc(
            session_id=session_id, trace_id=trace_id, limit=max(1, int(limit))
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                payload = json.loads(r["payload"])
            except Exception:
                payload = {}
            out.append(
                {
                    "trace_id": r["trace_id"],
                    "span_id": r["span_id"],
                    "parent_span_id": r["parent_span_id"],
                    "event_type": r["event_type"],
                    "payload": payload,
                    "timestamp": r["timestamp"],
                }
            )
        return out

    def get_turn_time_window(self, *, session_id: str, trace_id: str) -> tuple[str | None, str | None]:
        """Best-effort (start_ts, end_ts) for one trace_id in a session."""
        sid = str(session_id or "").strip()
        tid = str(trace_id or "").strip()
        if not sid or not tid:
            return None, None
        rows = self._trace_events_repo().list_event_type_timestamp_for_trace(
            session_id=sid, trace_id=tid
        )
        if not rows:
            return None, None
        start = None
        end = None
        for r in rows:
            et = str(r["event_type"] or "")
            ts = str(r["timestamp"] or "")
            if not start:
                start = ts
            end = ts
            if et == "turn_started":
                start = ts
            if et == "turn_finished":
                end = ts
        return start, end

    def list_messages_in_time_window(
        self, *, session_id: str, start_ts: str | None, end_ts: str | None, limit: int = 500
    ) -> list[dict[str, Any]]:
        sid = str(session_id or "").strip()
        if not sid:
            return []
        start = str(start_ts or "").strip()
        end = str(end_ts or "").strip()
        if not start or not end:
            return []
        lim = max(1, min(int(limit), 2000))
        return self._chat_messages_repo().list_messages_in_time_window(
            session_id=sid, start_ts=start, end_ts=end, limit=lim
        )

    # ----------------------------
    # Tenant / User / Bind Codes
    # ----------------------------
    def create_tenant(self, name: str) -> dict[str, Any]:
        tid = str(uuid.uuid4())
        ts = utc_now_iso()
        nm = str(name or "").strip() or "Team"
        self._tenant_repo().insert_tenant(tenant_id=tid, name=nm, created_at=ts)
        return {"id": tid, "name": name, "created_at": ts}

    def delete_tenant(self, *, tenant_id: str) -> int:
        tid = str(tenant_id or "").strip()
        if not tid:
            return 0
        return self._tenant_repo().delete_tenant(tenant_id=tid)

    def list_tenants(self, *, limit: int = 200) -> list[dict[str, Any]]:
        return self._tenant_repo().list_tenants(limit=max(1, int(limit)))

    def create_user(self, *, tenant_id: str, display_name: str, role: str) -> dict[str, Any]:
        uid = str(uuid.uuid4())
        ts = utc_now_iso()
        username = (str(display_name or "").strip() or "user").lower().replace(" ", "_")
        repo = self._app_users_repo()
        suffix = repo.count_by_tenant_username(tenant_id=str(tenant_id), username=username)
        if suffix > 0:
            username = f"{username}_{suffix+1}"
        disp = str(display_name or "").strip() or "User"
        repo.insert_user(
            user_id=uid,
            tenant_id=str(tenant_id),
            username=username,
            display_name=disp,
            role=str(role or "member"),
            password_hash="",
            is_active=1,
            created_at=ts,
            avatar_attachment_id=None,
        )
        return {
            "id": uid,
            "tenant_id": tenant_id,
            "username": username,
            "display_name": display_name,
            "role": role,
            "is_active": True,
            "created_at": ts,
        }

    def list_users(
        self,
        *,
        tenant_id: str,
        limit: int = 500,
        offset: int = 0,
        q: str | None = None,
        include_inactive: bool = True,
    ) -> list[dict[str, Any]]:
        return self._app_users_repo().list_users_for_tenant(
            tenant_id=str(tenant_id),
            limit=limit,
            offset=offset,
            q=q,
            include_inactive=include_inactive,
        )

    def get_user_by_username(self, *, tenant_id: str, username: str) -> dict[str, Any] | None:
        return self._app_users_repo().fetch_by_tenant_and_username(
            tenant_id=str(tenant_id), username=str(username)
        )

    def get_user_by_username_global(self, *, username: str) -> dict[str, Any] | None:
        return self._app_users_repo().fetch_first_by_username_global(username=str(username))

    def get_user_by_id(self, *, tenant_id: str, user_id: str) -> dict[str, Any] | None:
        return self._app_users_repo().fetch_by_tenant_and_id(
            tenant_id=str(tenant_id), user_id=str(user_id)
        )

    def create_user_account(
        self,
        *,
        tenant_id: str,
        username: str,
        display_name: str,
        role: str,
        password_hash: str,
        is_active: bool = True,
    ) -> dict[str, Any]:
        uid = str(uuid.uuid4())
        ts = utc_now_iso()
        self._app_users_repo().insert_user(
            user_id=uid,
            tenant_id=str(tenant_id),
            username=str(username).strip(),
            display_name=str(display_name).strip() or str(username).strip(),
            role=str(role or "member"),
            password_hash=str(password_hash or ""),
            is_active=1 if is_active else 0,
            created_at=ts,
            avatar_attachment_id=None,
        )
        return self.get_user_by_id(tenant_id=tenant_id, user_id=uid) or {}

    def update_user_account(
        self,
        *,
        tenant_id: str,
        user_id: str,
        display_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        password_hash: str | None = None,
        avatar_attachment_id: str | None = None,
    ) -> bool:
        return self._app_users_repo().update_user_account(
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            display_name=display_name,
            role=role,
            is_active=is_active,
            password_hash=password_hash,
            avatar_attachment_id=avatar_attachment_id,
        )

    def delete_user_account(self, *, tenant_id: str, user_id: str) -> int:
        return self._app_users_repo().delete_user_account(tenant_id=str(tenant_id), user_id=str(user_id))

    def upsert_user_permission(self, *, tenant_id: str, user_id: str, permission: str) -> None:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO user_permission (tenant_id, user_id, permission, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(tenant_id), str(user_id), str(permission), ts),
            )

    def delete_user_permission(self, *, tenant_id: str, user_id: str, permission: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM user_permission WHERE tenant_id = ? AND user_id = ? AND permission = ?",
                (str(tenant_id), str(user_id), str(permission)),
            )
        return int(cur.rowcount or 0)

    def list_user_permissions(self, *, tenant_id: str, user_id: str, role: str | None = None) -> list[str]:
        out: set[str] = set()
        role_name = str(role or "").strip()
        with self._connect() as conn:
            if role_name:
                rows = conn.execute(
                    "SELECT permission FROM role_permission WHERE role = ? ORDER BY permission ASC",
                    (role_name,),
                ).fetchall()
                out.update(str(r["permission"]) for r in rows)
            rows2 = conn.execute(
                """
                SELECT permission FROM user_permission
                WHERE tenant_id = ? AND user_id = ?
                ORDER BY permission ASC
                """,
                (str(tenant_id), str(user_id)),
            ).fetchall()
            out.update(str(r["permission"]) for r in rows2)
        return sorted(out)

    def get_user_workspace_path_allowlist(self, *, tenant_id: str, user_id: str) -> dict[str, Any] | None:
        tid = str(tenant_id or "").strip()
        uid = str(user_id or "").strip()
        if not tid or not uid:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT tenant_id, user_id, extra_roots, allow_any_path, allow_high_risk_public_tools, updated_at
                FROM user_workspace_path_allowlist
                WHERE tenant_id = ? AND user_id = ?
                LIMIT 1
                """,
                (tid, uid),
            ).fetchone()
        if not row:
            return None
        return {
            "tenant_id": str(row["tenant_id"] or ""),
            "user_id": str(row["user_id"] or ""),
            "extra_roots": str(row["extra_roots"] or ""),
            "allow_any_path": bool(int(row["allow_any_path"] or 0)),
            "allow_high_risk_public_tools": bool(int(row["allow_high_risk_public_tools"] or 0)),
            "updated_at": str(row["updated_at"] or ""),
        }

    def list_user_workspace_extra_roots_union(self) -> list[str]:
        """All ``|``-separated extra roots from every ``user_workspace_path_allowlist`` row.

        Intended for **admin/diagnostics** only. MCP filesystem argv must use per-session policy
        (see ``collect_filesystem_mcp_extra_roots(..., policy_session_id=...)``), not this union,
        so one user cannot inherit another user's roots.
        """
        out: list[str] = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT extra_roots FROM user_workspace_path_allowlist WHERE length(trim(extra_roots)) > 0"
            ).fetchall()
        for r in rows:
            raw = str(r["extra_roots"] or "")
            for part in raw.split("|"):
                s = part.strip().strip('"').strip("'")
                if s:
                    out.append(s)
        return out

    def upsert_user_workspace_path_allowlist(
        self,
        *,
        tenant_id: str,
        user_id: str,
        extra_roots: str,
        allow_any_path: bool,
        allow_high_risk_public_tools: bool = False,
    ) -> None:
        tid = str(tenant_id or "").strip()
        uid = str(user_id or "").strip()
        if not tid or not uid:
            return
        ts = utc_now_iso()
        roots = str(extra_roots or "")
        if len(roots) > 16000:
            roots = roots[:16000]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_workspace_path_allowlist (
                    tenant_id, user_id, extra_roots, allow_any_path, allow_high_risk_public_tools, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, user_id) DO UPDATE SET
                    extra_roots = excluded.extra_roots,
                    allow_any_path = excluded.allow_any_path,
                    allow_high_risk_public_tools = excluded.allow_high_risk_public_tools,
                    updated_at = excluded.updated_at
                """,
                (
                    tid,
                    uid,
                    roots,
                    1 if allow_any_path else 0,
                    1 if allow_high_risk_public_tools else 0,
                    ts,
                ),
            )

    def create_auth_session(
        self,
        *,
        session_token_hash: str,
        tenant_id: str,
        user_id: str,
        role: str,
        expires_at: str,
    ) -> None:
        ts = utc_now_iso()
        self._auth_sessions_repo().insert_session(
            session_token_hash=str(session_token_hash),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            role=str(role),
            created_at=ts,
            expires_at=str(expires_at),
            last_seen_at=ts,
        )

    def revoke_auth_session(self, *, session_token_hash: str) -> int:
        ts = utc_now_iso()
        return self._auth_sessions_repo().revoke_one(session_token_hash=str(session_token_hash), revoked_at=ts)

    def revoke_all_auth_sessions(self) -> int:
        ts = utc_now_iso()
        return self._auth_sessions_repo().revoke_all_active(revoked_at=ts)

    def get_auth_session(self, *, session_token_hash: str) -> dict[str, Any] | None:
        return self._auth_sessions_repo().fetch_by_hash(session_token_hash=str(session_token_hash))

    def touch_auth_session(self, *, session_token_hash: str) -> None:
        ts = utc_now_iso()
        self._auth_sessions_repo().touch(session_token_hash=str(session_token_hash), last_seen_at=ts)

    def add_admin_audit_log(
        self,
        *,
        actor_tenant_id: str,
        actor_user_id: str,
        action: str,
        target_type: str,
        target_id: str,
        status: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO admin_audit_log
                    (actor_tenant_id, actor_user_id, action, target_type, target_id, status, detail, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(actor_tenant_id),
                    str(actor_user_id),
                    str(action),
                    str(target_type),
                    str(target_id),
                    str(status),
                    json.dumps(detail or {}, ensure_ascii=False, default=str),
                    ts,
                ),
            )

    def list_admin_audit_logs(
        self,
        *,
        tenant_id: str | None = None,
        action: str | None = None,
        actor_user_id: str | None = None,
        status: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        lim = max(1, min(int(limit), 500))
        off = max(0, int(offset))
        clauses: list[str] = []
        params: list[Any] = []
        tid = str(tenant_id or "").strip()
        act = str(action or "").strip()
        actor = str(actor_user_id or "").strip()
        st = str(status or "").strip()
        if tid:
            clauses.append("l.actor_tenant_id = ?")
            params.append(tid)
        if act:
            clauses.append("l.action = ?")
            params.append(act)
        if actor:
            clauses.append("l.actor_user_id = ?")
            params.append(actor)
        if st:
            clauses.append("l.status = ?")
            params.append(st)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT l.actor_tenant_id, l.actor_user_id, l.action, l.target_type, l.target_id, l.status, l.detail,
                   l.timestamp, u.username AS actor_username, u.display_name AS actor_display_name
            FROM admin_audit_log l
            LEFT JOIN app_user u ON u.tenant_id = l.actor_tenant_id AND u.id = l.actor_user_id
            {where_sql}
            ORDER BY l.id DESC
            LIMIT ?
            OFFSET ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params + [lim, off])).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                detail = json.loads(r["detail"])
            except Exception:
                detail = {}
            out.append(
                {
                    "actor_tenant_id": r["actor_tenant_id"],
                    "actor_user_id": r["actor_user_id"],
                    "actor_username": str(r["actor_username"] or "") if r["actor_username"] is not None else "",
                    "actor_display_name": str(r["actor_display_name"] or "") if r["actor_display_name"] is not None else "",
                    "action": r["action"],
                    "target_type": r["target_type"],
                    "target_id": r["target_id"],
                    "status": r["status"],
                    "detail": detail,
                    "timestamp": r["timestamp"],
                }
            )
        return out

    def count_admin_audit_logs(
        self,
        *,
        tenant_id: str | None = None,
        action: str | None = None,
        actor_user_id: str | None = None,
        status: str | None = None,
    ) -> int:
        clauses: list[str] = []
        params: list[Any] = []
        tid = str(tenant_id or "").strip()
        act = str(action or "").strip()
        actor = str(actor_user_id or "").strip()
        st = str(status or "").strip()
        if tid:
            clauses.append("actor_tenant_id = ?")
            params.append(tid)
        if act:
            clauses.append("action = ?")
            params.append(act)
        if actor:
            clauses.append("actor_user_id = ?")
            params.append(actor)
        if st:
            clauses.append("status = ?")
            params.append(st)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT COUNT(1) AS c FROM admin_audit_log {where_sql}"
        with self._connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        return int((row["c"] if row and row["c"] is not None else 0) or 0)

    def upsert_channel_identity(
        self,
        *,
        tenant_id: str,
        channel: str,
        external_user_id: str,
        user_id: str,
    ) -> None:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO channel_identity (tenant_id, channel, external_user_id, user_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, channel, external_user_id) DO UPDATE SET
                    user_id = excluded.user_id
                """,
                (str(tenant_id), str(channel), str(external_user_id), str(user_id), ts),
            )

    def upsert_channel_identity_v2(
        self,
        *,
        tenant_id: str,
        channel: str,
        account_id: str,
        external_user_id: str,
        user_id: str,
    ) -> None:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO channel_identity_v2 (tenant_id, channel, account_id, external_user_id, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, channel, account_id, external_user_id) DO UPDATE SET
                    user_id = excluded.user_id
                """,
                (str(tenant_id), str(channel), str(account_id), str(external_user_id), str(user_id), ts),
            )

    def resolve_user_by_channel_identity(
        self, *, channel: str, external_user_id: str
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT ci.tenant_id, ci.user_id, u.display_name, u.role
                FROM channel_identity ci
                JOIN app_user u ON u.id = ci.user_id
                WHERE ci.channel = ? AND ci.external_user_id = ?
                LIMIT 1
                """,
                (str(channel), str(external_user_id)),
            ).fetchone()
        if not row:
            return None
        return {
            "tenant_id": row["tenant_id"],
            "user_id": row["user_id"],
            "display_name": row["display_name"],
            "role": row["role"],
        }

    def resolve_user_by_channel_identity_v2(
        self, *, channel: str, account_id: str, external_user_id: str
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT ci.tenant_id, ci.user_id, u.display_name, u.role
                FROM channel_identity_v2 ci
                JOIN app_user u ON u.id = ci.user_id
                WHERE ci.channel = ? AND ci.account_id = ? AND ci.external_user_id = ?
                LIMIT 1
                """,
                (str(channel), str(account_id), str(external_user_id)),
            ).fetchone()
        if not row:
            return None
        return {
            "tenant_id": row["tenant_id"],
            "user_id": row["user_id"],
            "display_name": row["display_name"],
            "role": row["role"],
        }

    def upsert_user_channel_account(
        self,
        *,
        tenant_id: str,
        user_id: str,
        channel: str,
        account_id: str,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        is_active: bool = True,
    ) -> None:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_channel_account
                    (tenant_id, user_id, channel, account_id, name, config, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, user_id, channel, account_id) DO UPDATE SET
                    name = excluded.name,
                    config = excluded.config,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at
                """,
                (
                    str(tenant_id),
                    str(user_id),
                    str(channel),
                    str(account_id),
                    str(name or "").strip(),
                    json.dumps(config or {}, ensure_ascii=False, default=str),
                    1 if is_active else 0,
                    ts,
                    ts,
                ),
            )

    def find_user_by_channel_account(self, *, channel: str, account_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT uca.tenant_id, uca.user_id, uca.channel, uca.account_id, uca.name, uca.config, uca.is_active,
                       u.display_name, u.role
                FROM user_channel_account uca
                JOIN app_user u ON u.id = uca.user_id
                WHERE uca.channel = ? AND uca.account_id = ? AND uca.is_active = 1
                ORDER BY uca.updated_at DESC
                LIMIT 1
                """,
                (str(channel), str(account_id)),
            ).fetchone()
        if not row:
            return None
        try:
            cfg = json.loads(row["config"])
        except Exception:
            cfg = {}
        return {
            "tenant_id": row["tenant_id"],
            "user_id": row["user_id"],
            "channel": row["channel"],
            "account_id": row["account_id"],
            "name": str(row["name"] or "").strip(),
            "display_name": row["display_name"],
            "role": row["role"],
            "config": cfg,
            "is_active": bool(int(row["is_active"] or 0)),
        }

    def list_user_channel_accounts(
        self, *, tenant_id: str, user_id: str, channel: str = "wecom", include_inactive: bool = True
    ) -> list[dict[str, Any]]:
        where = ["uca.tenant_id = ?", "uca.user_id = ?", "uca.channel = ?"]
        params: list[Any] = [str(tenant_id), str(user_id), str(channel)]
        if not include_inactive:
            where.append("uca.is_active = 1")
        sql = f"""
            SELECT uca.tenant_id, uca.user_id, uca.channel, uca.account_id, uca.name, uca.config, uca.is_active,
                   uca.created_at, uca.updated_at
            FROM user_channel_account uca
            WHERE {' AND '.join(where)}
            ORDER BY uca.updated_at DESC, uca.account_id ASC
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                cfg = json.loads(row["config"])
            except Exception:
                cfg = {}
            out.append(
                {
                    "tenant_id": row["tenant_id"],
                    "user_id": row["user_id"],
                    "channel": row["channel"],
                    "account_id": row["account_id"],
                    "name": str(row["name"] or "").strip(),
                    "config": cfg,
                    "is_active": bool(int(row["is_active"] or 0)),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return out

    def delete_user_channel_account(self, *, tenant_id: str, user_id: str, channel: str, account_id: str) -> int:
        tid, uid, aid = str(tenant_id), str(user_id), str(account_id)
        if str(channel) == "wecom":
            self.delete_setting(f"wecom:bot_secret:{tid}:{uid}:{aid}")
            self.delete_setting(f"wecom:agent_secret:{tid}:{uid}:{aid}")
        with self._connect() as conn:
            cur = conn.execute(
                """
                DELETE FROM user_channel_account
                WHERE tenant_id = ? AND user_id = ? AND channel = ? AND account_id = ?
                """,
                (tid, uid, str(channel), aid),
            )
            return int(cur.rowcount or 0)

    def backfill_user_channel_account_names(self, *, channel: str = "wecom") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE user_channel_account
                SET name = account_id
                WHERE channel = ? AND TRIM(COALESCE(name, '')) = ''
                """,
                (str(channel),),
            )
            return int(cur.rowcount or 0)

    def create_bind_code(self, *, tenant_id: str, role: str, code: str) -> dict[str, Any]:
        ts = utc_now_iso()
        self._bind_code_repo().insert_bind_code(
            code=str(code), tenant_id=str(tenant_id), role=str(role), created_at=ts
        )
        return {"code": code, "tenant_id": tenant_id, "role": role, "created_at": ts}

    def consume_bind_code(
        self, *, code: str, channel: str, external_user_id: str, display_name: str | None = None
    ) -> dict[str, Any] | None:
        """Consume a bind code and create/bind a new user. Returns binding info, or None if invalid/used."""
        code = str(code or "").strip()
        if not code:
            return None
        row = self._bind_code_repo().fetch_by_code(code=code)
        if not row or row.get("used_at"):
            return None
        tenant_id = str(row["tenant_id"])
        role = str(row["role"] or "member")
        user = self.create_user(tenant_id=tenant_id, display_name=display_name or "User", role=role)
        self.upsert_channel_identity(
            tenant_id=tenant_id,
            channel=channel,
            external_user_id=external_user_id,
            user_id=str(user["id"]),
        )
        ts = utc_now_iso()
        self._bind_code_repo().mark_used(
            code=code, used_at=ts, used_by_external_user_id=str(external_user_id)
        )
        return {"tenant_id": tenant_id, "user_id": user["id"], "role": role}

    def list_bind_codes(self, *, tenant_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        lim = max(1, int(limit))
        rows = self._bind_code_repo().list_bind_codes(tenant_id=tenant_id, limit=lim)
        return [
            {
                "code": r["code"],
                "tenant_id": r["tenant_id"],
                "role": r["role"],
                "created_at": r["created_at"],
                "used_at": r["used_at"],
                "used_by_external_user_id": r["used_by_external_user_id"],
            }
            for r in rows
        ]

    def list_channel_identities(
        self, *, tenant_id: str | None = None, channel: str | None = None, limit: int = 300
    ) -> list[dict[str, Any]]:
        lim = max(1, int(limit))
        where = []
        params: list[Any] = []
        if tenant_id:
            where.append("ci.tenant_id = ?")
            params.append(str(tenant_id))
        if channel:
            where.append("ci.channel = ?")
            params.append(str(channel))
        wsql = ("WHERE " + " AND ".join(where)) if where else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT ci.tenant_id, ci.channel, ci.external_user_id, ci.user_id, ci.created_at,
                       u.display_name, u.role
                FROM channel_identity ci
                JOIN app_user u ON u.id = ci.user_id
                {wsql}
                ORDER BY ci.created_at DESC
                LIMIT ?
                """,
                (*params, lim),
            ).fetchall()
        return [
            {
                "tenant_id": r["tenant_id"],
                "channel": r["channel"],
                "external_user_id": r["external_user_id"],
                "user_id": r["user_id"],
                "display_name": r["display_name"],
                "role": r["role"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def list_channel_identities_v2(
        self,
        *,
        tenant_id: str | None = None,
        channel: str | None = None,
        account_id: str | None = None,
        user_id: str | None = None,
        limit: int = 300,
    ) -> list[dict[str, Any]]:
        lim = max(1, int(limit))
        where = []
        params: list[Any] = []
        if tenant_id:
            where.append("ci.tenant_id = ?")
            params.append(str(tenant_id))
        if channel:
            where.append("ci.channel = ?")
            params.append(str(channel))
        if account_id:
            where.append("ci.account_id = ?")
            params.append(str(account_id))
        if user_id:
            where.append("ci.user_id = ?")
            params.append(str(user_id))
        wsql = ("WHERE " + " AND ".join(where)) if where else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT ci.tenant_id, ci.channel, ci.account_id, ci.external_user_id, ci.user_id, ci.created_at,
                       u.display_name, u.role,
                       COALESCE(uca.name, '') AS account_name
                FROM channel_identity_v2 ci
                JOIN app_user u ON u.id = ci.user_id
                LEFT JOIN user_channel_account uca
                  ON uca.tenant_id = ci.tenant_id
                 AND uca.user_id = ci.user_id
                 AND uca.channel = ci.channel
                 AND uca.account_id = ci.account_id
                {wsql}
                ORDER BY ci.created_at DESC
                LIMIT ?
                """,
                (*params, lim),
            ).fetchall()
        return [
            {
                "tenant_id": r["tenant_id"],
                "channel": r["channel"],
                "account_id": r["account_id"],
                "account_name": str(r["account_name"] or "").strip(),
                "external_user_id": r["external_user_id"],
                "user_id": r["user_id"],
                "display_name": r["display_name"],
                "role": r["role"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_or_create_channel_session(
        self,
        *,
        tenant_id: str,
        channel: str,
        external_chat_id: str,
        external_user_id: str,
        session_title: str,
    ) -> str:
        """Return a stable session_id for a given channel chat context."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT session_id
                FROM channel_session
                WHERE tenant_id = ? AND channel = ? AND external_chat_id = ? AND external_user_id = ?
                LIMIT 1
                """,
                (str(tenant_id), str(channel), str(external_chat_id), str(external_user_id)),
            ).fetchone()
        if row and row["session_id"]:
            return str(row["session_id"])
        sess = self.create_session(session_title)
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO channel_session
                    (tenant_id, channel, external_chat_id, external_user_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(tenant_id), str(channel), str(external_chat_id), str(external_user_id), str(sess.id), ts),
            )
        return str(sess.id)

    def get_or_create_channel_session_v2(
        self,
        *,
        tenant_id: str,
        channel: str,
        account_id: str,
        external_chat_id: str,
        external_user_id: str,
        session_title: str,
    ) -> str:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT session_id
                FROM channel_session_v2
                WHERE tenant_id = ? AND channel = ? AND account_id = ? AND external_chat_id = ? AND external_user_id = ?
                LIMIT 1
                """,
                (str(tenant_id), str(channel), str(account_id), str(external_chat_id), str(external_user_id)),
            ).fetchone()
        if row and row["session_id"]:
            return str(row["session_id"])
        sess = self.create_session(session_title)
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO channel_session_v2
                    (tenant_id, channel, account_id, external_chat_id, external_user_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (str(tenant_id), str(channel), str(account_id), str(external_chat_id), str(external_user_id), str(sess.id), ts),
            )
        return str(sess.id)

    def backfill_ui_session_owner_from_channel_v2(self) -> int:
        return self._ui_session_owner_repo().backfill_from_channel_v2(created_at=utc_now_iso())

    # ----------------------------
    # Oclaw tasks
    # ----------------------------
    def oclaw_task_create(
        self,
        *,
        tenant_id: str,
        session_id: str,
        task_type: str = "async_turn",
        payload: dict[str, Any] | None = None,
    ) -> OclawTask:
        tid = str(uuid.uuid4())
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO oclaw_task
                    (id, tenant_id, session_id, task_type, status, payload, result, attempt_count, claimed_by, lease_expires_at, last_error, created_at, updated_at, finished_at)
                VALUES (?, ?, ?, ?, 'queued', ?, '{}', 0, NULL, NULL, '', ?, ?, NULL)
                """,
                (
                    tid,
                    str(tenant_id),
                    str(session_id),
                    str(task_type or "async_turn"),
                    json.dumps(payload or {}, ensure_ascii=False),
                    ts,
                    ts,
                ),
            )
        got = self.oclaw_task_get(task_id=tid)
        if not got:
            raise RuntimeError("failed to create oclaw task")
        return got

    def oclaw_task_claim(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 90,
        task_type: str | None = None,
    ) -> OclawTask | None:
        now = datetime.now(timezone.utc)
        lease_expires = (now + timedelta(seconds=max(15, min(int(lease_seconds or 90), 1800)))).isoformat()
        now_iso = now.isoformat()
        with self._connect() as conn:
            where = "(status = 'queued' OR (status = 'claimed' AND (lease_expires_at IS NULL OR lease_expires_at <= ?)))"
            params: list[Any] = [now_iso]
            tt = str(task_type or "").strip()
            if tt:
                where = f"{where} AND task_type = ?"
                params.append(tt)
            row = conn.execute(
                f"""
                SELECT id FROM oclaw_task
                WHERE {where}
                ORDER BY created_at ASC
                LIMIT 1
                """,
                tuple(params),
            ).fetchone()
            if not row:
                return None
            task_id = str(row["id"])
            cur = conn.execute(
                """
                UPDATE oclaw_task
                SET status = 'claimed',
                    attempt_count = attempt_count + 1,
                    claimed_by = ?,
                    lease_expires_at = ?,
                    updated_at = ?
                WHERE id = ?
                  AND (status = 'queued' OR (status = 'claimed' AND (lease_expires_at IS NULL OR lease_expires_at <= ?)))
                """,
                (str(worker_id), lease_expires, now_iso, task_id, now_iso),
            )
            if not cur.rowcount:
                return None
        return self.oclaw_task_get(task_id=task_id)

    def oclaw_task_finish(self, *, task_id: str, result: dict[str, Any] | None = None) -> bool:
        ts = utc_now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE oclaw_task
                SET status = 'done',
                    result = ?,
                    lease_expires_at = NULL,
                    last_error = '',
                    updated_at = ?,
                    finished_at = ?
                WHERE id = ?
                """,
                (json.dumps(result or {}, ensure_ascii=False), ts, ts, str(task_id)),
            )
        return bool(cur.rowcount and cur.rowcount > 0)

    def oclaw_task_fail(self, *, task_id: str, error: str, result: dict[str, Any] | None = None) -> bool:
        ts = utc_now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE oclaw_task
                SET status = 'failed',
                    result = ?,
                    lease_expires_at = NULL,
                    last_error = ?,
                    updated_at = ?,
                    finished_at = ?
                WHERE id = ?
                """,
                (json.dumps(result or {}, ensure_ascii=False), str(error or "")[:2000], ts, ts, str(task_id)),
            )
        return bool(cur.rowcount and cur.rowcount > 0)

    def oclaw_task_get(self, *, task_id: str, tenant_id: str | None = None) -> OclawTask | None:
        where = "id = ?"
        params: list[Any] = [str(task_id)]
        if tenant_id:
            where += " AND tenant_id = ?"
            params.append(str(tenant_id))
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, tenant_id, session_id, task_type, status, payload, result, attempt_count, claimed_by, lease_expires_at, last_error, created_at, updated_at, finished_at
                FROM oclaw_task
                WHERE """ + where + """
                LIMIT 1
                """,
                tuple(params),
            ).fetchone()
        if not row:
            return None
        return OclawTask(
            id=str(row["id"]),
            tenant_id=str(row["tenant_id"]),
            session_id=str(row["session_id"]),
            task_type=str(row["task_type"]),
            status=str(row["status"]),
            payload=str(row["payload"] or "{}"),
            result=str(row["result"] or "{}"),
            attempt_count=int(row["attempt_count"] or 0),
            claimed_by=str(row["claimed_by"]) if row["claimed_by"] else None,
            lease_expires_at=str(row["lease_expires_at"]) if row["lease_expires_at"] else None,
            last_error=str(row["last_error"] or ""),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            finished_at=str(row["finished_at"]) if row["finished_at"] else None,
        )

    def oclaw_task_list(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        tenant_id: str | None = None,
        session_id: str | None = None,
    ) -> list[OclawTask]:
        lim = max(1, min(int(limit or 50), 500))
        where = ""
        params: list[Any] = []
        if status:
            where = "status = ?"
            params.append(str(status))
        if tenant_id:
            where = f"{where} AND tenant_id = ?" if where else "tenant_id = ?"
            params.append(str(tenant_id))
        if session_id:
            where = f"{where} AND session_id = ?" if where else "session_id = ?"
            params.append(str(session_id))
        where_clause = f"WHERE {where}" if where else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, tenant_id, session_id, task_type, status, payload, result, attempt_count, claimed_by, lease_expires_at, last_error, created_at, updated_at, finished_at
                FROM oclaw_task
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, lim),
            ).fetchall()
        out: list[OclawTask] = []
        for row in rows:
            out.append(
                OclawTask(
                    id=str(row["id"]),
                    tenant_id=str(row["tenant_id"]),
                    session_id=str(row["session_id"]),
                    task_type=str(row["task_type"]),
                    status=str(row["status"]),
                    payload=str(row["payload"] or "{}"),
                    result=str(row["result"] or "{}"),
                    attempt_count=int(row["attempt_count"] or 0),
                    claimed_by=str(row["claimed_by"]) if row["claimed_by"] else None,
                    lease_expires_at=str(row["lease_expires_at"]) if row["lease_expires_at"] else None,
                    last_error=str(row["last_error"] or ""),
                    created_at=str(row["created_at"]),
                    updated_at=str(row["updated_at"]),
                    finished_at=str(row["finished_at"]) if row["finished_at"] else None,
                )
            )
        return out

    def oclaw_run_upsert(
        self,
        *,
        run_id: str,
        tenant_id: str,
        session_id: str,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO oclaw_run(run_id, tenant_id, session_id, status, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    str(run_id),
                    str(tenant_id),
                    str(session_id),
                    str(status),
                    json.dumps(payload or {}, ensure_ascii=False),
                    ts,
                    ts,
                ),
            )
        return True

    def oclaw_attempt_append(
        self,
        *,
        run_id: str,
        tenant_id: str,
        session_id: str,
        attempt_no: int,
        status: str,
        reason: str = "",
        payload: dict[str, Any] | None = None,
    ) -> int:
        ts = utc_now_iso()
        with self._connect() as conn:
            if self._use_pg:
                cur = conn.execute(
                    """
                    INSERT INTO oclaw_attempt(run_id, tenant_id, session_id, attempt_no, status, reason, payload, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id
                    """,
                    (
                        str(run_id),
                        str(tenant_id),
                        str(session_id),
                        int(attempt_no),
                        str(status),
                        str(reason or ""),
                        json.dumps(payload or {}, ensure_ascii=False),
                        ts,
                    ),
                )
                row = cur.fetchone()
                return int(row["id"]) if row else 0
            cur = conn.execute(
                """
                INSERT INTO oclaw_attempt(run_id, tenant_id, session_id, attempt_no, status, reason, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(run_id),
                    str(tenant_id),
                    str(session_id),
                    int(attempt_no),
                    str(status),
                    str(reason or ""),
                    json.dumps(payload or {}, ensure_ascii=False),
                    ts,
                ),
            )
            return int(cur.lastrowid or 0)

    def oclaw_attempt_list(self, *, run_id: str, limit: int = 30) -> list[dict[str, Any]]:
        lim = max(1, min(int(limit or 30), 200))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, run_id, tenant_id, session_id, attempt_no, status, reason, payload, created_at
                FROM oclaw_attempt
                WHERE run_id = ?
                ORDER BY attempt_no ASC
                LIMIT ?
                """,
                (str(run_id), lim),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": int(row["id"]),
                    "run_id": str(row["run_id"]),
                    "tenant_id": str(row["tenant_id"]),
                    "session_id": str(row["session_id"]),
                    "attempt_no": int(row["attempt_no"]),
                    "status": str(row["status"]),
                    "reason": str(row["reason"] or ""),
                    "payload": str(row["payload"] or "{}"),
                    "created_at": str(row["created_at"]),
                }
            )
        return out

    def oclaw_run_get(self, *, run_id: str, tenant_id: str | None = None) -> OclawRun | None:
        where = "run_id = ?"
        params: list[Any] = [str(run_id)]
        if tenant_id:
            where += " AND tenant_id = ?"
            params.append(str(tenant_id))
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT run_id, tenant_id, session_id, status, payload, created_at, updated_at
                FROM oclaw_run
                WHERE {where}
                LIMIT 1
                """,
                tuple(params),
            ).fetchone()
        if not row:
            return None
        return OclawRun(
            run_id=str(row["run_id"]),
            tenant_id=str(row["tenant_id"]),
            session_id=str(row["session_id"]),
            status=str(row["status"]),
            payload=str(row["payload"] or "{}"),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def oclaw_run_list(
        self,
        *,
        tenant_id: str,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[OclawRun]:
        lim = max(1, min(int(limit or 50), 300))
        where = "tenant_id = ?"
        params: list[Any] = [str(tenant_id)]
        if session_id:
            where += " AND session_id = ?"
            params.append(str(session_id))
        if status:
            where += " AND status = ?"
            params.append(str(status))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT run_id, tenant_id, session_id, status, payload, created_at, updated_at
                FROM oclaw_run
                WHERE {where}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (*params, lim),
            ).fetchall()
        out: list[OclawRun] = []
        for row in rows:
            out.append(
                OclawRun(
                    run_id=str(row["run_id"]),
                    tenant_id=str(row["tenant_id"]),
                    session_id=str(row["session_id"]),
                    status=str(row["status"]),
                    payload=str(row["payload"] or "{}"),
                    created_at=str(row["created_at"]),
                    updated_at=str(row["updated_at"]),
                )
            )
        return out

    # ----------------------------
    # Todo items
    # ----------------------------
    def todo_create(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        title: str,
        due_at: str | None = None,
        assignee_user_id: str | None = None,
    ) -> dict[str, Any]:
        tid = str(uuid.uuid4())
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO todo_item
                    (id, tenant_id, owner_user_id, assignee_user_id, title, due_at, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tid,
                    str(tenant_id),
                    str(owner_user_id),
                    str(assignee_user_id) if assignee_user_id else None,
                    str(title or "").strip(),
                    str(due_at) if due_at else None,
                    "open",
                    ts,
                    ts,
                ),
            )
        return {
            "id": tid,
            "tenant_id": tenant_id,
            "owner_user_id": owner_user_id,
            "assignee_user_id": assignee_user_id,
            "title": title,
            "due_at": due_at,
            "status": "open",
            "created_at": ts,
            "updated_at": ts,
        }

    def todo_list(
        self,
        *,
        tenant_id: str,
        assignee_user_id: str | None = None,
        status: str | None = "open",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        lim = max(1, min(int(limit), 200))
        where = ["tenant_id = ?"]
        params: list[Any] = [str(tenant_id)]
        if assignee_user_id:
            where.append("assignee_user_id = ?")
            params.append(str(assignee_user_id))
        if status:
            where.append("status = ?")
            params.append(str(status))
        wsql = " AND ".join(where)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, tenant_id, owner_user_id, assignee_user_id, title, due_at, status, created_at, updated_at
                FROM todo_item
                WHERE {wsql}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (*params, lim),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "tenant_id": r["tenant_id"],
                "owner_user_id": r["owner_user_id"],
                "assignee_user_id": r["assignee_user_id"],
                "title": r["title"],
                "due_at": r["due_at"],
                "status": r["status"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def todo_set_status(self, *, tenant_id: str, todo_id: str, status: str) -> bool:
        ts = utc_now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE todo_item
                SET status = ?, updated_at = ?
                WHERE tenant_id = ? AND id = ?
                """,
                (str(status), ts, str(tenant_id), str(todo_id)),
            )
        return bool(cur.rowcount and cur.rowcount > 0)

    def todo_assign(self, *, tenant_id: str, todo_id: str, assignee_user_id: str) -> bool:
        ts = utc_now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE todo_item
                SET assignee_user_id = ?, updated_at = ?
                WHERE tenant_id = ? AND id = ?
                """,
                (str(assignee_user_id), ts, str(tenant_id), str(todo_id)),
            )
        return bool(cur.rowcount and cur.rowcount > 0)

    def upsert_whatsapp_known_group(
        self,
        *,
        tenant_id: str,
        account_id: str,
        group_jid: str,
        group_name: str = "",
    ) -> None:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO whatsapp_known_group (tenant_id, account_id, group_jid, group_name, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, account_id, group_jid) DO UPDATE SET
                    group_name = CASE WHEN excluded.group_name != '' THEN excluded.group_name ELSE whatsapp_known_group.group_name END,
                    last_seen_at = excluded.last_seen_at
                """,
                (str(tenant_id), str(account_id), str(group_jid), str(group_name or ""), ts),
            )

    def list_whatsapp_known_groups(
        self,
        *,
        tenant_id: str | None = None,
        account_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if tenant_id:
            clauses.append("tenant_id = ?")
            params.append(str(tenant_id))
        if account_id:
            clauses.append("account_id = ?")
            params.append(str(account_id))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT tenant_id, account_id, group_jid, group_name, last_seen_at
                FROM whatsapp_known_group
                {where}
                ORDER BY last_seen_at DESC
                """,
                tuple(params),
            ).fetchall()
        return [
            {
                "tenant_id": str(r[0] or ""),
                "account_id": str(r[1] or ""),
                "group_jid": str(r[2] or ""),
                "group_name": str(r[3] or ""),
                "last_seen_at": str(r[4] or ""),
            }
            for r in rows
        ]

    def get_whatsapp_alert_binding(
        self,
        *,
        tenant_id: str,
        account_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT tenant_id, account_id, group_jid, group_name, enabled, updated_at
                FROM whatsapp_alert_binding
                WHERE tenant_id = ? AND account_id = ?
                """,
                (str(tenant_id), str(account_id)),
            ).fetchone()
        if row is None:
            return None
        return {
            "tenant_id": str(row[0] or ""),
            "account_id": str(row[1] or ""),
            "group_jid": str(row[2] or ""),
            "group_name": str(row[3] or ""),
            "enabled": bool(int(row[4] or 0)),
            "updated_at": str(row[5] or ""),
        }

    def upsert_whatsapp_alert_binding(
        self,
        *,
        tenant_id: str,
        account_id: str,
        group_jid: str,
        group_name: str = "",
        enabled: bool = True,
    ) -> dict[str, Any]:
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO whatsapp_alert_binding (tenant_id, account_id, group_jid, group_name, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, account_id) DO UPDATE SET
                    group_jid = excluded.group_jid,
                    group_name = excluded.group_name,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (str(tenant_id), str(account_id), str(group_jid), str(group_name or ""), 1 if enabled else 0, ts),
            )
        out = self.get_whatsapp_alert_binding(tenant_id=tenant_id, account_id=account_id)
        return out or {}

    def enqueue_channel_outbound_message(
        self,
        *,
        channel: str,
        chat_id: str,
        text: str,
        tenant_id: str = "",
        account_id: str = "",
        source: str = "",
    ) -> str:
        import uuid

        msg_id = uuid.uuid4().hex
        ts = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO channel_outbound_message
                    (id, tenant_id, channel, account_id, chat_id, text, status, source, created_at, error)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, '')
                """,
                (msg_id, str(tenant_id), str(channel), str(account_id), str(chat_id), str(text), str(source), ts),
            )
        return msg_id

    def list_pending_channel_outbound_messages(
        self,
        *,
        channel: str,
        account_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        lim = max(1, min(int(limit), 100))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, tenant_id, channel, account_id, chat_id, text, source, created_at
                FROM channel_outbound_message
                WHERE channel = ? AND account_id = ? AND status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (str(channel), str(account_id), lim),
            ).fetchall()
        return [
            {
                "id": str(r[0] or ""),
                "tenant_id": str(r[1] or ""),
                "channel": str(r[2] or ""),
                "account_id": str(r[3] or ""),
                "chat_id": str(r[4] or ""),
                "text": str(r[5] or ""),
                "source": str(r[6] or ""),
                "created_at": str(r[7] or ""),
            }
            for r in rows
        ]

    def ack_channel_outbound_message(
        self,
        *,
        message_id: str,
        ok: bool,
        error: str = "",
    ) -> bool:
        ts = utc_now_iso()
        status = "sent" if ok else "failed"
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE channel_outbound_message
                SET status = ?, sent_at = ?, error = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status, ts, str(error or ""), str(message_id)),
            )
        return bool(cur.rowcount and cur.rowcount > 0)
