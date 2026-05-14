"""Translate SQLite-oriented SQL to PostgreSQL for psycopg execution."""

from __future__ import annotations

import re
from typing import Any


def scrub_nul_bytes_from_text(s: str | None) -> str | None:
    """PostgreSQL ``TEXT`` / ``VARCHAR`` reject U+0000; SQLite allows it.

    Strip NULs from any string bound for PG text columns so assistant/tool rows
    persist instead of failing the whole ``INSERT`` after the user row succeeded.
    """
    if s is None:
        return None
    if "\x00" not in s:
        return s
    return s.replace("\x00", "")


def scrub_nul_bytes_from_jsonable(obj: Any) -> Any:
    """Recursively remove NUL from strings inside dict/list before ``json.dumps``.

    ``json.dumps`` encodes embedded NUL as the six-character ``\\u0000`` escape; a
    plain ``TEXT`` scrub on the serialized JSON would not remove the decoded NUL
    after reload, and PostgreSQL still rejects a true NUL inside string values.
    """
    if isinstance(obj, str):
        return obj.replace("\x00", "") if "\x00" in obj else obj
    if isinstance(obj, dict):
        return {k: scrub_nul_bytes_from_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_nul_bytes_from_jsonable(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(scrub_nul_bytes_from_jsonable(v) for v in obj)
    return obj


def qmarks_to_percent(sql: str) -> str:
    """Replace ``?`` placeholders outside single-quoted strings with ``%s`` (psycopg)."""
    out: list[str] = []
    i = 0
    in_single = False
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and (i == 0 or sql[i - 1] != "\\"):
            in_single = not in_single
            out.append(ch)
            i += 1
            continue
        if ch == "?" and not in_single:
            out.append("%s")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def rewrite_sqlite_extensions_for_postgres(sql: str) -> str:
    """Rewrite SQLite-only INSERT forms to PostgreSQL-compatible SQL (still uses ``?``)."""
    s = sql
    repls: list[tuple[str, str]] = [
        (
            """INSERT OR REPLACE INTO ui_session_owner(session_id, tenant_id, user_id, created_at)
                VALUES (?, ?, ?, ?)""",
            """INSERT INTO ui_session_owner(session_id, tenant_id, user_id, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (session_id) DO UPDATE SET
                  tenant_id = EXCLUDED.tenant_id,
                  user_id = EXCLUDED.user_id,
                  created_at = EXCLUDED.created_at""",
        ),
        (
            """INSERT OR IGNORE INTO ui_session_owner(session_id, tenant_id, user_id, created_at)
                SELECT DISTINCT cs.session_id, cs.tenant_id, ci.user_id, ?
                FROM channel_session_v2 cs
                JOIN channel_identity_v2 ci
                  ON ci.tenant_id = cs.tenant_id
                 AND ci.channel = cs.channel
                 AND ci.account_id = cs.account_id
                 AND ci.external_user_id = cs.external_user_id
                WHERE cs.session_id IS NOT NULL AND cs.session_id != ''""",
            """INSERT INTO ui_session_owner(session_id, tenant_id, user_id, created_at)
                SELECT DISTINCT cs.session_id, cs.tenant_id, ci.user_id, ?
                FROM channel_session_v2 cs
                JOIN channel_identity_v2 ci
                  ON ci.tenant_id = cs.tenant_id
                 AND ci.channel = cs.channel
                 AND ci.account_id = cs.account_id
                 AND ci.external_user_id = cs.external_user_id
                WHERE cs.session_id IS NOT NULL AND cs.session_id != ''
                ON CONFLICT (session_id) DO NOTHING""",
        ),
        (
            """INSERT OR IGNORE INTO ui_session_owner(session_id, tenant_id, user_id, created_at)
                SELECT s.id, ?, ?, COALESCE(s.created_at, ?)
                FROM chat_session s
                WHERE NOT EXISTS (SELECT 1 FROM ui_session_owner o WHERE o.session_id = s.id)""",
            """INSERT INTO ui_session_owner(session_id, tenant_id, user_id, created_at)
                SELECT s.id, ?, ?, COALESCE(s.created_at, ?)
                FROM chat_session s
                WHERE NOT EXISTS (SELECT 1 FROM ui_session_owner o WHERE o.session_id = s.id)
                ON CONFLICT (session_id) DO NOTHING""",
        ),
        (
            """INSERT OR IGNORE INTO ui_session_owner(session_id, tenant_id, user_id, created_at)
                VALUES (?, ?, ?, ?)""",
            """INSERT INTO ui_session_owner(session_id, tenant_id, user_id, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (session_id) DO NOTHING""",
        ),
        (
            """INSERT OR IGNORE INTO llm_profile
                (id, name, mode, model, base_url, api_key, updated_at, is_builtin, hide_in_ui, owner_user_id)
            VALUES (?, ?, 'ollama', ?, ?, NULL, ?, 1, 0, NULL)""",
            """INSERT INTO llm_profile
                (id, name, mode, model, base_url, api_key, updated_at, is_builtin, hide_in_ui, owner_user_id)
            VALUES (?, ?, 'ollama', ?, ?, NULL, ?, 1, 0, NULL)
            ON CONFLICT (id) DO NOTHING""",
        ),
        (
            """INSERT OR IGNORE INTO llm_profile
                (id, name, mode, model, base_url, api_key, updated_at, is_builtin, hide_in_ui, owner_user_id)
            VALUES (?, ?, 'rule', NULL, NULL, NULL, ?, 1, 1, NULL)""",
            """INSERT INTO llm_profile
                (id, name, mode, model, base_url, api_key, updated_at, is_builtin, hide_in_ui, owner_user_id)
            VALUES (?, ?, 'rule', NULL, NULL, NULL, ?, 1, 1, NULL)
            ON CONFLICT (id) DO NOTHING""",
        ),
        (
            """INSERT OR IGNORE INTO role_permission(role, permission, created_at)
                    VALUES (?, ?, ?)""",
            """INSERT INTO role_permission(role, permission, created_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT (role, permission) DO NOTHING""",
        ),
        (
            """INSERT OR IGNORE INTO attachment_acl
                    (attachment_id, tenant_id, user_id, session_id, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
            """INSERT INTO attachment_acl
                    (attachment_id, tenant_id, user_id, session_id, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (attachment_id, tenant_id, user_id, session_id, source) DO NOTHING""",
        ),
        (
            """INSERT OR IGNORE INTO attachment_acl
                            (attachment_id, tenant_id, user_id, session_id, source, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)""",
            """INSERT INTO attachment_acl
                            (attachment_id, tenant_id, user_id, session_id, source, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT (attachment_id, tenant_id, user_id, session_id, source) DO NOTHING""",
        ),
        (
            """INSERT OR IGNORE INTO llm_profile_user_grant
                    (id, tenant_id, profile_id, user_id, created_at, created_by_user_id)
                VALUES (?, ?, ?, ?, ?, ?)""",
            """INSERT INTO llm_profile_user_grant
                    (id, tenant_id, profile_id, user_id, created_at, created_by_user_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, profile_id, user_id) DO NOTHING""",
        ),
        (
            """INSERT OR IGNORE INTO llm_profile_tenant_grant
                    (id, tenant_id, profile_id, created_at, created_by_user_id)
                VALUES (?, ?, ?, ?, ?)""",
            """INSERT INTO llm_profile_tenant_grant
                    (id, tenant_id, profile_id, created_at, created_by_user_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, profile_id) DO NOTHING""",
        ),
        (
            """INSERT OR IGNORE INTO user_permission (tenant_id, user_id, permission, created_at)
                VALUES (?, ?, ?, ?)""",
            """INSERT INTO user_permission (tenant_id, user_id, permission, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (tenant_id, user_id, permission) DO NOTHING""",
        ),
        (
            """INSERT OR IGNORE INTO channel_session
                    (tenant_id, channel, external_chat_id, external_user_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
            """INSERT INTO channel_session
                    (tenant_id, channel, external_chat_id, external_user_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, channel, external_chat_id, external_user_id) DO NOTHING""",
        ),
        (
            """INSERT OR IGNORE INTO channel_session_v2
                    (tenant_id, channel, account_id, external_chat_id, external_user_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
            """INSERT INTO channel_session_v2
                    (tenant_id, channel, account_id, external_chat_id, external_user_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, channel, account_id, external_chat_id, external_user_id) DO NOTHING""",
        ),
    ]
    for old, new in repls:
        if old in s:
            s = s.replace(old, new, 1)
    if "INSERT OR IGNORE INTO" in s:
        s = re.sub(
            r"INSERT\s+OR\s+IGNORE\s+INTO\s+(\w+)\s+",
            r"INSERT INTO \1 ",
            s,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if "ON CONFLICT" not in s.upper():
            s = s.rstrip() + "\nON CONFLICT DO NOTHING"
    if "INSERT OR REPLACE INTO" in s.upper():
        raise ValueError(
            "unsupported INSERT OR REPLACE for PostgreSQL; extend svc.persistence.pg_compat"
        )
    return s


def adapt_sql_for_postgres(sql: str) -> str:
    return qmarks_to_percent(rewrite_sqlite_extensions_for_postgres(sql))


__all__ = [
    "adapt_sql_for_postgres",
    "qmarks_to_percent",
    "rewrite_sqlite_extensions_for_postgres",
    "scrub_nul_bytes_from_jsonable",
    "scrub_nul_bytes_from_text",
]
