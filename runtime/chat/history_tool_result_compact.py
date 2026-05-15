from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from runtime.chat.media_redact import redact_embedded_image_blobs
from runtime.direct_loop import (
    _OCLAW_TOOL_RESULT_HARD_CAP_CHARS,
    _image_tool_result_replay_cap_chars,
    _video_tool_result_replay_cap_chars,
)


@dataclass(frozen=True)
class HistoryCompactionResult:
    ok: bool
    session_id: str
    scanned_tool_messages: int = 0
    compacted_tool_messages: int = 0
    rewritten_all_tool_messages: int = 0
    skipped_already_guarded: int = 0
    max_original_chars_seen: int = 0
    cap_chars: int = 0
    detail: str = ""


def _chat_message_id_content(row: Any) -> tuple[int, str]:
    """Normalize SQLite Row/tuple vs PostgreSQL dict_row for ``select id, content``."""
    if isinstance(row, dict):
        return int(row["id"]), str(row.get("content") or "")
    return int(row[0]), str(row[1] or "")  # type: ignore[index]


def _json_dumps_safe(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"ok": False, "error": "not_json_serializable"}, ensure_ascii=False)


def _guard_tool_result_text_for_history(
    *,
    store: Any,
    raw: str,
    cap_chars: int,
    image_cap_chars: int,
    video_cap_chars: int,
) -> tuple[str, bool]:
    """Return (new_raw, changed) following the same strategy as context replay guard."""
    text = str(raw or "")
    if not text:
        return text, False
    # Redact embedded blobs first (same as context guard).
    try:
        p0 = json.loads(text)
        p1 = redact_embedded_image_blobs(p0)
        text = _json_dumps_safe(p1)
    except Exception:
        pass

    # If already guarded, do not rewrite again.
    try:
        obj0 = json.loads(text)
        if isinstance(obj0, dict) and (obj0.get("_tool_result_guarded") or obj0.get("_image_tool_result_guarded") or obj0.get("_video_tool_result_guarded")):
            return text, False
    except Exception:
        obj0 = None

    ok = None
    error_code = ""
    error = ""
    obj: dict[str, Any] | None = None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            obj = parsed
            ok = obj.get("ok")
            error_code = str(obj.get("error_code") or "").strip()
            error = str(obj.get("error") or "").strip()
    except Exception:
        obj = None

    if isinstance(obj, dict):
        task = str(obj.get("task") or "").strip().lower()
        t = str(obj.get("text") or "")
        has_attachment_id = bool(str(obj.get("attachment_id") or "").strip())
        if task in {"describe", "ocr"} and has_attachment_id and len(t) > int(image_cap_chars):
            preview = t[: int(image_cap_chars)] + "\n...<image_tool_result_truncated_for_context_replay>"
            guarded_obj = dict(obj)
            guarded_obj["text"] = preview
            guarded_obj["_image_tool_result_guarded"] = True
            guarded_obj["image_result_original_chars"] = len(t)
            guarded_obj["image_result_replay_cap_chars"] = int(image_cap_chars)
            guarded_obj["image_result_hint"] = (
                "Image analysis result was truncated for context replay. "
                "Refine query_image_attachment(question=...) for narrower evidence. / "
                "图片分析结果在上下文回放中已截断，请缩小 query_image_attachment 的问题范围。"
            )
            return _json_dumps_safe(guarded_obj), True
        if task == "transcript" and has_attachment_id and len(t) > int(video_cap_chars):
            preview = t[: int(video_cap_chars)] + "\n...<video_tool_result_truncated_for_context_replay>"
            guarded_obj = dict(obj)
            guarded_obj["text"] = preview
            guarded_obj["_video_tool_result_guarded"] = True
            guarded_obj["video_result_original_chars"] = len(t)
            guarded_obj["video_result_replay_cap_chars"] = int(video_cap_chars)
            return _json_dumps_safe(guarded_obj), True

    if len(text) <= int(cap_chars):
        return text, False

    preview = text[: max(1, min(4000, int(cap_chars) - 400))] + "\n...<tool_result_guard_truncated>"
    guarded_obj = {
        "ok": bool(ok) if ok is not None else None,
        "error_code": error_code,
        "error": error,
        "_tool_result_guarded": True,
        "original_chars": len(text),
        "guard_cap_chars": int(cap_chars),
        "preview": preview,
        "hint": (
            "Tool output was too large for safe context replay; it was truncated for history storage. "
            "Use narrower queries (e.g., smaller glob/max_results) or adjust AIA_TOOL_LLM_MESSAGE_MAX_CHARS. / "
            "工具输出过大，已压缩写回历史；请缩小范围或配置 AIA_TOOL_LLM_MESSAGE_MAX_CHARS。"
        ),
    }
    return _json_dumps_safe(guarded_obj), True


def compact_tool_results_in_session_history(
    *,
    store: Any,
    session_id: str,
    cap_chars: int | None = None,
    limit_messages: int = 5000,
    rewrite_all: bool = True,
) -> HistoryCompactionResult:
    """Rewrite overlarge `role=tool` chat_message.content in DB using the replay-guard strategy."""
    sid = str(session_id or "").strip()
    if not sid:
        return HistoryCompactionResult(ok=False, session_id="", detail="session_id_required")
    cap = max(4096, min(int(cap_chars or _OCLAW_TOOL_RESULT_HARD_CAP_CHARS), 500_000))
    image_cap = int(_image_tool_result_replay_cap_chars(store))
    video_cap = int(_video_tool_result_replay_cap_chars(store))
    scanned = 0
    compacted = 0
    rewritten_all = 0
    skipped = 0
    max_seen = 0

    # We only need to scan tool messages; fetching ids+content is enough.
    with store._connect() as conn:  # noqa: SLF001
        cur = conn.execute(
            "select id, content from chat_message where session_id=? and role='tool' "
            "order by id asc limit ?",
            (sid, max(1, min(int(limit_messages or 5000), 200_000))),
        )
        rows = cur.fetchall() or []
        for row in rows:
            mid, raw = _chat_message_id_content(row)
            scanned += 1
            txt = str(raw or "")
            max_seen = max(max_seen, len(txt))
            new_txt, changed = _guard_tool_result_text_for_history(
                store=store,
                raw=txt,
                cap_chars=cap,
                image_cap_chars=image_cap,
                video_cap_chars=video_cap,
            )
            # Defensive fallback: if content is still over cap but guard didn't report change,
            # force a minimal guard so polluted history can always be compacted.
            if (not changed) and len(txt) > int(cap):
                preview = txt[: max(1, min(4000, int(cap) - 400))] + "\n...<tool_result_guard_truncated>"
                new_txt = _json_dumps_safe(
                    {
                        "ok": None,
                        "error_code": "",
                        "error": "",
                        "_tool_result_guarded": True,
                        "original_chars": len(txt),
                        "guard_cap_chars": int(cap),
                        "preview": preview,
                        "hint": (
                            "Tool output was too large for safe context replay; it was truncated for history storage. / "
                            "工具输出过大，已压缩写回历史。"
                        ),
                    }
                )
                changed = True
            # Full rewrite mode: compact every tool_result row into guarded envelope,
            # even when current content is under cap. This keeps history bounded and
            # prevents heterogeneous huge payload persistence.
            if (not changed) and bool(rewrite_all):
                preview_cap = max(200, min(1200, int(cap) - 200))
                preview = txt[:preview_cap]
                if len(txt) > preview_cap:
                    preview += "\n...<tool_result_guard_truncated>"
                ok_val = None
                try:
                    _obj = json.loads(txt)
                    if isinstance(_obj, dict):
                        _ok = _obj.get("ok")
                        ok_val = bool(_ok) if _ok is not None else None
                except Exception:
                    ok_val = None
                new_txt = _json_dumps_safe(
                    {
                        "ok": ok_val,
                        "error_code": "",
                        "error": "",
                        "_tool_result_guarded": True,
                        "_history_full_rewrite": True,
                        "original_chars": len(txt),
                        "guard_cap_chars": int(cap),
                        "preview": preview,
                        "hint": (
                            "Tool result history was compacted by operator action. / "
                            "该工具结果历史已按运维操作统一压缩。"
                        ),
                    }
                )
                changed = (new_txt != txt)
                if changed:
                    rewritten_all += 1
            if not changed:
                # could be already guarded, or under cap
                if txt and ("_tool_result_guarded" in txt or "_image_tool_result_guarded" in txt or "_video_tool_result_guarded" in txt):
                    skipped += 1
                continue
            conn.execute("update chat_message set content=? where id=? and session_id=?", (new_txt, int(mid), sid))
            compacted += 1

    return HistoryCompactionResult(
        ok=True,
        session_id=sid,
        scanned_tool_messages=int(scanned),
        compacted_tool_messages=int(compacted),
        rewritten_all_tool_messages=int(rewritten_all),
        skipped_already_guarded=int(skipped),
        max_original_chars_seen=int(max_seen),
        cap_chars=int(cap),
        detail="ok",
    )


__all__ = [
    "HistoryCompactionResult",
    "compact_tool_results_in_session_history",
]

