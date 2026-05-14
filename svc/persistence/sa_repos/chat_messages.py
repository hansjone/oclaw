"""chat_message access via SQLAlchemy Core."""

from __future__ import annotations

import json
from typing import Any, Mapping

from sqlalchemy import delete, exists, func, insert, literal, select, update
from sqlalchemy.engine import Engine

from svc.persistence.db.tables import chat_message, chat_session
from svc.persistence.sqlite_store import (
    ChatMessage,
    SessionMessagesMeta,
    _tool_row_assistant_message_id,
    _trim_messages_start_index,
    utc_now_iso,
)


def _sql_text_required(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (bytes, bytearray, memoryview)):
        try:
            return bytes(v).decode("utf-8", errors="replace")
        except Exception:
            return ""
    return str(v)


def _sql_text_optional_plain(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray, memoryview)):
        try:
            s = bytes(v).decode("utf-8", errors="replace")
        except Exception:
            return None
        s = s.strip()
        return s if s else None
    s = str(v).strip()
    return s if s else None


def _sql_text_optional_jsonish(v: Any) -> str | None:
    """Normalize TEXT/JSON columns across SQLite + PostgreSQL drivers (bytes/memoryview/dict)."""
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray, memoryview)):
        try:
            s = bytes(v).decode("utf-8", errors="replace")
        except Exception:
            return None
        return s if s.strip() else None
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, default=str)
    s = str(v).strip()
    return s if s else None


def _row_to_chat_message(r: Mapping[str, Any]) -> ChatMessage:
    return ChatMessage(
        id=int(r["id"]),
        session_id=str(r["session_id"]),
        role=str(r["role"]),
        content=_sql_text_required(r.get("content")),
        tool_calls=_sql_text_optional_jsonish(r.get("tool_calls")),
        attachments=_sql_text_optional_jsonish(r.get("attachments")),
        turn_uuid=_sql_text_optional_plain(r.get("turn_uuid")),
        event_type=_sql_text_optional_plain(r.get("event_type")),
        event_payload=_sql_text_optional_jsonish(r.get("event_payload")),
        timestamp=str(r["timestamp"]),
    )


class ChatMessagesSaRepository:
    """Phase-4 SA migration: chat_message CRUD + session last_message_at touch."""

    __slots__ = ("_engine",)

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def insert_message_and_touch_session(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        tool_calls: str | None,
        attachments: str | None,
        turn_uuid: str | None,
        event_type: str | None,
        event_payload: str | None,
        timestamp: str,
    ) -> int:
        sid = str(session_id if session_id is not None else "")
        with self._engine.begin() as conn:
            stmt = (
                insert(chat_message)
                .values(
                    session_id=sid,
                    role=str(role),
                    content=str(content),
                    tool_calls=tool_calls,
                    attachments=attachments,
                    turn_uuid=turn_uuid,
                    event_type=event_type,
                    event_payload=event_payload,
                    timestamp=str(timestamp),
                )
                .returning(chat_message.c.id)
            )
            msg_id = int(conn.execute(stmt).scalar_one())
            conn.execute(
                update(chat_session)
                .where(chat_session.c.id == sid)
                .values(last_message_at=str(timestamp))
            )
        return msg_id

    def delete_message_and_refresh_session(self, *, session_id: str, message_id: int) -> bool:
        sid = str(session_id or "").strip()
        mid = int(message_id or 0)
        if not sid or mid <= 0:
            return False
        with self._engine.begin() as conn:
            res = conn.execute(
                delete(chat_message).where(
                    chat_message.c.session_id == sid,
                    chat_message.c.id == mid,
                )
            )
            if int(res.rowcount or 0) <= 0:
                return False
            last_ts = conn.execute(
                select(func.max(chat_message.c.timestamp)).where(chat_message.c.session_id == sid)
            ).scalar_one_or_none()
            last_s = str(last_ts or "").strip() or None
            conn.execute(
                update(chat_session)
                .where(chat_session.c.id == sid)
                .values(last_message_at=last_s)
            )
        return True

    def update_message_content(
        self,
        *,
        session_id: str,
        message_id: int,
        content: str,
        event_payload_text: str | None,
    ) -> bool:
        sid = str(session_id or "").strip()
        mid = int(message_id or 0)
        if not sid or mid <= 0:
            return False
        with self._engine.begin() as conn:
            res = conn.execute(
                update(chat_message)
                .where(chat_message.c.session_id == sid, chat_message.c.id == mid)
                .values(
                    content=str(content or ""),
                    event_payload=func.coalesce(literal(event_payload_text), chat_message.c.event_payload),
                )
            )
            return int(res.rowcount or 0) > 0

    def get_messages_recent_asc(self, *, session_id: str, limit: int) -> list[ChatMessage]:
        if limit <= 0:
            return []
        sid = str(session_id or "").strip()
        if not sid:
            return []
        lim = max(1, min(int(limit), 2000))
        ids_sq = (
            select(chat_message.c.id)
            .where(chat_message.c.session_id == sid)
            .order_by(chat_message.c.id.desc())
            .limit(lim)
            .scalar_subquery()
        )
        stmt = (
            select(
                chat_message.c.id,
                chat_message.c.session_id,
                chat_message.c.role,
                chat_message.c.content,
                chat_message.c.tool_calls,
                chat_message.c.attachments,
                chat_message.c.turn_uuid,
                chat_message.c.event_type,
                chat_message.c.event_payload,
                chat_message.c.timestamp,
            )
            .where(chat_message.c.session_id == sid, chat_message.c.id.in_(ids_sq))
            .order_by(chat_message.c.id.asc())
        )
        prepended: set[int] = set()
        with self._engine.connect() as conn:
            rows: list[dict[str, Any]] = [dict(r) for r in conn.execute(stmt).mappings().all()]
            while rows:
                first = rows[0]
                if str(first.get("role") or "") != "tool":
                    break
                aid = _tool_row_assistant_message_id(first.get("tool_calls"))
                if aid is None:
                    break
                first_id = int(first["id"])
                if aid >= first_id:
                    break
                if any(int(r["id"]) == int(aid) for r in rows):
                    break
                if int(aid) in prepended:
                    break
                arow = conn.execute(
                    select(
                        chat_message.c.id,
                        chat_message.c.session_id,
                        chat_message.c.role,
                        chat_message.c.content,
                        chat_message.c.tool_calls,
                        chat_message.c.attachments,
                        chat_message.c.turn_uuid,
                        chat_message.c.event_type,
                        chat_message.c.event_payload,
                        chat_message.c.timestamp,
                    )
                    .where(chat_message.c.session_id == sid, chat_message.c.id == int(aid))
                    .limit(1)
                ).mappings().first()
                if not arow:
                    break
                prepended.add(int(aid))
                rows.insert(0, dict(arow))
        return [_row_to_chat_message(r) for r in rows]

    def get_messages_after_id(
        self, *, session_id: str, after_id: int, limit: int
    ) -> list[ChatMessage]:
        sid = str(session_id or "").strip()
        if not sid:
            return []
        aid = int(after_id or 0)
        lim = max(1, min(int(limit), 2000))
        stmt = (
            select(
                chat_message.c.id,
                chat_message.c.session_id,
                chat_message.c.role,
                chat_message.c.content,
                chat_message.c.tool_calls,
                chat_message.c.attachments,
                chat_message.c.turn_uuid,
                chat_message.c.event_type,
                chat_message.c.event_payload,
                chat_message.c.timestamp,
            )
            .where(chat_message.c.session_id == sid, chat_message.c.id > aid)
            .order_by(chat_message.c.id.asc())
            .limit(lim)
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_row_to_chat_message(dict(r)) for r in rows]

    def count_messages(self, *, session_id: str) -> int:
        key = str(session_id if session_id is not None else "")
        with self._engine.connect() as conn:
            n = conn.execute(
                select(func.count()).select_from(chat_message).where(chat_message.c.session_id == key)
            ).scalar_one()
        return int(n or 0)

    def session_messages_meta(self, *, session_id: str) -> SessionMessagesMeta:
        key = str(session_id if session_id is not None else "")
        with self._engine.connect() as conn:
            row = conn.execute(
                select(
                    func.count().label("c"),
                    func.max(chat_message.c.id).label("last_id"),
                    func.max(chat_message.c.timestamp).label("last_ts"),
                )
                .where(chat_message.c.session_id == key)
            ).mappings().first()
        return SessionMessagesMeta(
            session_id=session_id,
            message_count=int(row["c"] or 0) if row else 0,
            last_message_id=int(row["last_id"]) if row and row.get("last_id") is not None else None,
            last_message_at=str(row["last_ts"]) if row and row.get("last_ts") is not None else None,
        )

    def last_message_id(self, *, session_id: str) -> int | None:
        key = str(session_id if session_id is not None else "")
        with self._engine.connect() as conn:
            m = conn.execute(
                select(func.max(chat_message.c.id)).where(chat_message.c.session_id == key)
            ).scalar_one_or_none()
        if m is None:
            return None
        return int(m)

    def list_messages_in_time_window(
        self, *, session_id: str, start_ts: str, end_ts: str, limit: int
    ) -> list[dict[str, Any]]:
        sid = str(session_id or "").strip()
        start = str(start_ts or "").strip()
        end = str(end_ts or "").strip()
        if not sid or not start or not end:
            return []
        lim = max(1, min(int(limit), 2000))
        stmt = (
            select(
                chat_message.c.id,
                chat_message.c.session_id,
                chat_message.c.role,
                chat_message.c.content,
                chat_message.c.tool_calls,
                chat_message.c.attachments,
                chat_message.c.turn_uuid,
                chat_message.c.event_type,
                chat_message.c.event_payload,
                chat_message.c.timestamp,
            )
            .where(
                chat_message.c.session_id == sid,
                chat_message.c.timestamp >= start,
                chat_message.c.timestamp <= end,
            )
            .order_by(chat_message.c.id.asc())
            .limit(lim)
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": int(r["id"] or 0),
                    "session_id": str(r["session_id"] or ""),
                    "role": str(r["role"] or ""),
                    "content": str(r["content"] or ""),
                    "tool_calls": r["tool_calls"],
                    "attachments": r["attachments"],
                    "turn_uuid": str(r["turn_uuid"] or ""),
                    "event_type": str(r["event_type"] or ""),
                    "event_payload": r["event_payload"],
                    "timestamp": str(r["timestamp"] or ""),
                }
            )
        return out

    def delete_messages_where_session_missing(self) -> int:
        """Delete ``chat_message`` rows whose ``session_id`` is not in ``chat_session`` (housekeeping)."""
        sess_exists = exists(
            select(1).select_from(chat_session).where(chat_session.c.id == chat_message.c.session_id)
        )
        with self._engine.begin() as conn:
            res = conn.execute(delete(chat_message).where(~sess_exists))
            return int(res.rowcount or 0)

    def fork_assert_anchor(self, *, source_session_id: str, up_to_message_id: int) -> None:
        """Raise ``ValueError`` unless ``up_to_message_id`` exists in ``source_session_id``."""
        src = str(source_session_id if source_session_id is not None else "")
        cap = int(up_to_message_id or 0)
        if not src or cap <= 0:
            raise ValueError("message not in session")
        with self._engine.connect() as conn:
            chk = conn.execute(
                select(chat_message.c.id)
                .where(chat_message.c.session_id == src, chat_message.c.id == cap)
                .limit(1)
            ).first()
        if not chk:
            raise ValueError("message not in session")

    def fork_copy_messages_to_session(
        self,
        *,
        source_session_id: str,
        up_to_message_id: int,
        new_session_id: str,
    ) -> None:
        """Copy messages with ``id <= up_to_message_id`` into ``new_session_id``; remap tool assistant ids."""
        src = str(source_session_id if source_session_id is not None else "")
        new_sid = str(new_session_id if new_session_id is not None else "")
        cap = int(up_to_message_id or 0)
        if not src or not new_sid or cap <= 0:
            raise ValueError("message not in session")
        with self._engine.begin() as conn:
            rows_list = list(
                conn.execute(
                    select(
                        chat_message.c.id,
                        chat_message.c.role,
                        chat_message.c.content,
                        chat_message.c.tool_calls,
                        chat_message.c.attachments,
                        chat_message.c.turn_uuid,
                        chat_message.c.event_type,
                        chat_message.c.event_payload,
                        chat_message.c.timestamp,
                    )
                    .where(chat_message.c.session_id == src, chat_message.c.id <= cap)
                    .order_by(chat_message.c.id.asc())
                ).mappings().all()
            )
            if not rows_list:
                raise ValueError("message not in session")
            id_map: dict[int, int] = {}
            for r in rows_list:
                old_id = int(r["id"])
                role = str(r["role"])
                tool_calls_text = r["tool_calls"]
                if role == "tool" and tool_calls_text:
                    try:
                        meta = json.loads(str(tool_calls_text))
                        if isinstance(meta, dict):
                            aid = meta.get("assistant_message_id")
                            if aid is not None:
                                new_aid = id_map.get(int(aid))
                                if new_aid is not None:
                                    meta = {**meta, "assistant_message_id": new_aid}
                                    tool_calls_text = json.dumps(meta, ensure_ascii=False)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass
                stmt = (
                    insert(chat_message)
                    .values(
                        session_id=new_sid,
                        role=role,
                        content=r["content"],
                        tool_calls=tool_calls_text,
                        attachments=r["attachments"],
                        turn_uuid=r["turn_uuid"],
                        event_type=r["event_type"],
                        event_payload=r["event_payload"],
                        timestamp=r["timestamp"],
                    )
                    .returning(chat_message.c.id)
                )
                new_id = int(conn.execute(stmt).scalar_one())
                id_map[old_id] = new_id
            last_ts = rows_list[-1]["timestamp"] if rows_list else utc_now_iso()
            conn.execute(
                update(chat_session)
                .where(chat_session.c.id == new_sid)
                .values(last_message_at=last_ts)
            )

    def trim_messages_keep_last(self, *, session_id: str, keep_last: int) -> None:
        """Delete older messages so at least ``keep_last`` newest rows remain (tool/assistant boundary aware)."""
        key = str(session_id if session_id is not None else "")
        kl = int(keep_last)
        if not key or kl <= 0:
            return
        with self._engine.connect() as conn:
            rows_list = [
                dict(r)
                for r in conn.execute(
                    select(chat_message.c.id, chat_message.c.role, chat_message.c.tool_calls)
                    .where(chat_message.c.session_id == key)
                    .order_by(chat_message.c.id.asc())
                ).mappings().all()
            ]
        start = _trim_messages_start_index(rows_list, kl)
        if start is None:
            return
        min_keep_id = int(rows_list[start]["id"])
        with self._engine.begin() as conn:
            conn.execute(
                delete(chat_message).where(
                    chat_message.c.session_id == key,
                    chat_message.c.id < min_keep_id,
                )
            )


__all__ = ["ChatMessagesSaRepository"]
