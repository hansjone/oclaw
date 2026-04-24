from __future__ import annotations

import json
from typing import Any

from oclaw.platform.persistence.sqlite_store import ChatMessage, SqliteStore


def export_session_json(store: SqliteStore, session_id: str, message_limit: int = 50_000) -> str:
    title = ""
    s = store.get_session(session_id)
    if s:
        title = s.title
    msgs = store.get_messages(session_id=session_id, limit=message_limit)
    payload: dict[str, Any] = {
        "session_id": session_id,
        "title": title,
        "messages": [_message_to_dict(m) for m in msgs],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def export_session_markdown(store: SqliteStore, session_id: str, message_limit: int = 50_000) -> str:
    s = store.get_session(session_id)
    title = (s.title if s else "") or session_id[:12]
    lines = [f"# {title}", "", f"Session: `{session_id}`", ""]
    for m in store.get_messages(session_id=session_id, limit=message_limit):
        lines.extend(_message_to_markdown_lines(m))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _message_to_dict(m: ChatMessage) -> dict[str, Any]:
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "tool_calls": m.tool_calls,
        "attachments": m.attachments,
        "timestamp": m.timestamp,
    }


def _message_to_markdown_lines(m: ChatMessage) -> list[str]:
    role = m.role.upper()
    ts = m.timestamp or ""
    head = f"## {role} · `{m.id}` · {ts}"
    body = m.content or ""
    if m.role == "tool" and m.tool_calls:
        head = f"## TOOL · `{m.id}` · {ts}"
    lines = [head, ""]
    if body.strip():
        lines.append(body)
        lines.append("")
    if m.tool_calls and m.role != "tool":
        lines.append("```json")
        lines.append(m.tool_calls)
        lines.append("```")
    elif m.tool_calls and m.role == "tool":
        lines.append(f"_meta_: `{m.tool_calls}`")
    if m.attachments:
        lines.append("_attachments_: see JSON export for full data.")
    return lines


__all__ = ["export_session_json", "export_session_markdown"]
