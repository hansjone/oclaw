from __future__ import annotations

from typing import Any

from oclaw.runtime.skill_installer import install_skill_from_registry_archive
from oclaw.runtime.tools.skills.clawhub_client import get_skill_detail as clawhub_get_skill_detail
from oclaw.runtime.tools.skills.clawhub_client import search_skills as clawhub_search_skills


def build_common_gateway_context(*, store: Any) -> dict[str, Any]:
    def _read_session_messages(session_key: str, limit: int) -> list[dict[str, Any]]:
        rows = store.get_messages(
            session_id=str(session_key or "").strip(),
            limit=max(1, min(int(limit or 100), 1000)),
        )
        return [
            {
                "id": int(getattr(m, "id", 0) or 0),
                "role": str(getattr(m, "role", "") or ""),
                "content": str(getattr(m, "content", "") or ""),
                "tool_calls": getattr(m, "tool_calls", None),
                "attachments": getattr(m, "attachments", None),
                "timestamp": str(getattr(m, "timestamp", "") or ""),
            }
            for m in rows
        ]

    def _list_sessions() -> list[dict[str, Any]]:
        rows = store.list_sessions(limit=200, offset=0)
        return [
            {
                "key": str(s.id),
                "sessionId": str(s.id),
                "title": str(s.title or ""),
                "createdAt": str(s.created_at or ""),
                "lastMessageAt": str(getattr(s, "last_message_at", "") or ""),
            }
            for s in rows
        ]

    def _get_session(session_key: str) -> dict[str, Any]:
        sess = store.get_session(str(session_key or "").strip())
        if not sess:
            return {}
        return {
            "key": str(sess.id),
            "sessionId": str(sess.id),
            "title": str(sess.title or ""),
            "createdAt": str(sess.created_at or ""),
            "lastMessageAt": str(getattr(sess, "last_message_at", "") or ""),
        }

    def _search_clawhub_skills(p: dict[str, Any]) -> list[dict[str, Any]]:
        q = str((p or {}).get("query") or "").strip()
        lim = int((p or {}).get("limit") or 20)
        return clawhub_search_skills(q, limit=lim)

    def _fetch_clawhub_skill_detail(p: dict[str, Any]) -> dict[str, Any]:
        slug = str((p or {}).get("slug") or "").strip()
        return clawhub_get_skill_detail(slug)

    def _install_skill_from_clawhub(p: dict[str, Any]) -> dict[str, Any]:
        slug = str((p or {}).get("slug") or "").strip()
        version = str((p or {}).get("version") or "").strip()
        force = bool((p or {}).get("force"))
        archive_url = str((p or {}).get("archiveUrl") or "").strip()
        if not archive_url and slug:
            d = clawhub_get_skill_detail(slug)
            if version:
                for v in (d.get("versions") or []):
                    if isinstance(v, dict) and str(v.get("version") or "").strip() == version:
                        archive_url = str(v.get("archiveUrl") or "").strip()
                        break
            if not archive_url:
                archive_url = str(d.get("archiveUrl") or "").strip()
        if not archive_url:
            return {"ok": False, "error": "archive_url_unavailable"}
        out = install_skill_from_registry_archive(store=store, archive_url=archive_url, overwrite=force)
        return {"ok": bool(out.ok), "result": out.__dict__}

    return {
        "store": store,
        "search_clawhub_skills": _search_clawhub_skills,
        "fetch_clawhub_skill_detail": _fetch_clawhub_skill_detail,
        "install_skill_from_clawhub": _install_skill_from_clawhub,
        "read_session_messages": _read_session_messages,
        "list_sessions": _list_sessions,
        "get_session": _get_session,
    }


__all__ = ["build_common_gateway_context"]
