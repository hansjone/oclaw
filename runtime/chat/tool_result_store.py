"""Persist full tool results for later fetch_tool_result while LLM sees compact payloads."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from svc.config.paths import attachments_dir

_REF_RE = re.compile(r"^tr:[0-9a-f]{32}$")
_SAVE_MIN_CHARS = 4_000
_FETCH_DEFAULT_MAX_CHARS = 120_000


def _root() -> Path:
    p = (attachments_dir() / "tool_results").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _session_dir(session_id: str) -> Path:
    sid = str(session_id or "").strip() or "_anon"
    digest = hashlib.sha256(sid.encode("utf-8", errors="ignore")).hexdigest()[:24]
    d = _root() / digest
    d.mkdir(parents=True, exist_ok=True)
    return d


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _json_size(obj: Any) -> int:
    try:
        return len(_json_dumps(obj))
    except Exception:
        return 0


def make_result_ref(*, session_id: str, tool_call_id: str, payload: Any) -> str:
    raw = f"{session_id}|{tool_call_id}|{_json_size(payload)}|{time.time_ns()}"
    return "tr:" + hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:32]


def is_tool_result_ref(value: str) -> bool:
    return bool(_REF_RE.fullmatch(str(value or "").strip().lower()))


def save_tool_result_blob(
    *,
    session_id: str,
    tool_call_id: str,
    result: Any,
    force: bool = False,
) -> str | None:
    """Store full tool JSON when large enough (or force=True). Returns result_ref or None."""
    sid = str(session_id or "").strip()
    if not sid:
        return None
    if not isinstance(result, dict):
        return None
    size = _json_size(result)
    if (not force) and size < int(_SAVE_MIN_CHARS):
        return None
    ref = make_result_ref(session_id=sid, tool_call_id=str(tool_call_id or ""), payload=result)
    path = _session_dir(sid) / f"{ref[3:]}.json"
    meta = {
        "result_ref": ref,
        "session_id": sid,
        "tool_call_id": str(tool_call_id or ""),
        "chars": int(size),
        "saved_at_ms": int(time.time() * 1000),
    }
    path.write_text(_json_dumps({"meta": meta, "result": result}), encoding="utf-8")
    return ref


def load_tool_result_blob(
    result_ref: str,
    *,
    session_id: str,
    max_chars: int | None = None,
) -> dict[str, Any]:
    ref = str(result_ref or "").strip().lower()
    sid = str(session_id or "").strip()
    if not is_tool_result_ref(ref):
        return {"ok": False, "error_code": "invalid_result_ref", "error": "invalid_result_ref"}
    if not sid:
        return {"ok": False, "error_code": "session_required", "error": "session_required"}
    path = _session_dir(sid) / f"{ref[3:]}.json"
    if not path.is_file():
        # Fallback: scan root for orphaned refs (session hash mismatch / migrate).
        found = None
        for child in _root().glob(f"*/{ref[3:]}.json"):
            found = child
            break
        if found is None:
            return {"ok": False, "error_code": "result_ref_not_found", "error": "result_ref_not_found", "result_ref": ref}
        path = found
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error_code": "result_ref_read_failed", "error": f"{type(exc).__name__}: {exc}"}
    meta = data.get("meta") if isinstance(data, dict) else None
    if isinstance(meta, dict):
        owner = str(meta.get("session_id") or "").strip()
        if owner and owner != sid:
            return {"ok": False, "error_code": "result_ref_session_mismatch", "error": "result_ref_session_mismatch"}
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, dict):
        return {"ok": False, "error_code": "result_ref_invalid_payload", "error": "result_ref_invalid_payload"}
    cap = int(_FETCH_DEFAULT_MAX_CHARS if max_chars is None else max_chars)
    cap = max(4_000, min(cap, 500_000))
    body = _json_dumps(result)
    if len(body) <= cap:
        out = dict(result)
        out["result_ref"] = ref
        out["_fetched_full"] = True
        return {"ok": True, "result_ref": ref, "result": out, "chars": len(body), "truncated": False}
    from runtime.chat.tool_runtime import truncate_tool_result_for_llm_messages

    slim = truncate_tool_result_for_llm_messages(result, max_chars=cap)
    if isinstance(slim, dict):
        slim = dict(slim)
        slim["result_ref"] = ref
        slim["_fetched_truncated"] = True
        slim["hint"] = (
            str(slim.get("hint") or "")
            + " Full blob still on disk; narrow the tool query or raise max_chars on fetch_tool_result."
        ).strip()
    return {
        "ok": True,
        "result_ref": ref,
        "result": slim,
        "chars": len(body),
        "truncated": True,
        "fetch_cap_chars": cap,
    }


def attach_result_ref(payload: dict[str, Any], *, result_ref: str | None) -> dict[str, Any]:
    if not result_ref or not isinstance(payload, dict):
        return payload
    out = dict(payload)
    out["result_ref"] = str(result_ref)
    if out.get("_truncated_for_llm") or out.get("_tool_result_guarded") or out.get("_history_compacted"):
        out["fetch_tool"] = "fetch_tool_result"
        hint = str(out.get("hint") or "").strip()
        extra = (
            f"Full tool output stored as result_ref={result_ref}. "
            f"Call fetch_tool_result(result_ref=\"{result_ref}\") when you need details."
        )
        out["hint"] = f"{hint} {extra}".strip() if hint else extra
    return out


__all__ = [
    "attach_result_ref",
    "is_tool_result_ref",
    "load_tool_result_blob",
    "make_result_ref",
    "save_tool_result_blob",
]
