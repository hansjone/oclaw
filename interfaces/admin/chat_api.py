"""Admin-mounted chat REST API (non-Streamlit). Uses same bearer auth as other /admin/api routes."""

from __future__ import annotations

import base64
import json
import queue
import threading
import os
from collections.abc import Callable, Iterator
from typing import Any
from pathlib import Path

from fastapi import APIRouter, Body, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse

from oclaw.runtime.operations.mcp_env import apply_gateway_mcp_env_to_os
from oclaw.runtime.agents.specialists import SPECIALIST_IDS
from oclaw.runtime.agents.factory import build_gateway_executor
from oclaw.runtime.chat.agent import GenerationInterrupted
from oclaw.platform.config.paths import db_path
from oclaw.platform.files.attachment_assets import AttachmentAssetStore
from oclaw.platform.files.file_attachments import (
    DEFAULT_TABULAR_CELL_CHARS,
    DEFAULT_TABULAR_COLUMNS,
    DEFAULT_MAX_EXCEL_SHEETS,
    DEFAULT_TABULAR_ROWS_READ,
    clear_attachment_limits_cache,
    process_file_data,
)
from oclaw.platform.files.session_export import export_session_json, export_session_markdown
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.gateway import OclawGateway
from oclaw.runtime.types import StandardMessage, normalize_interaction_mode, normalize_requested_specialist


def _oclaw_config_path() -> Path:
    raw = str(os.getenv("AIA_OCLAW_CONFIG_PATH") or "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else p.resolve()
    # repo_root/src/admin/chat_api.py -> repo_root
    return Path(__file__).resolve().parents[2] / "oclaw" / "oclaw.json"


def _wiki_root_from_config() -> Path | None:
    cfg_path = _oclaw_config_path()
    if not cfg_path.exists():
        return None
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    plugins = cfg.get("plugins") if isinstance(cfg, dict) else {}
    entries = plugins.get("entries") if isinstance(plugins, dict) else {}
    wiki_entry = entries.get("memory-wiki") if isinstance(entries, dict) else {}
    root_cfg = str(wiki_entry.get("wiki_root") or "").strip()
    if not root_cfg:
        return None
    root = Path(root_cfg)
    if not root.is_absolute():
        root = (Path(__file__).resolve().parents[2] / root).resolve()
    return root

_CHAT_MSG_LIMIT = 256
_SESSION_TITLE_MAX_LEN = 120
_AVATAR_UPLOAD_MAX_BYTES = 2 * 1024 * 1024
_AVATAR_MIMES = frozenset({"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"})

_CHAT_STOP_EVENTS: dict[str, threading.Event] = {}
_CHAT_STOP_LOCK = threading.Lock()
_DISPATCH_REASON_LABELS: dict[str, dict[str, str]] = {
    "manager_no_specialist_fallback": {
        "zh": "无可用专家，回退通用",
        "en": "No specialist; fallback to generalist",
    },
    "dynamic_agent_build_failed": {
        "zh": "动态专家构建失败",
        "en": "Dynamic agent build failed",
    },
    "manager_factory_failed": {
        "zh": "专家执行器创建失败",
        "en": "Specialist executor factory failed",
    },
    "manager_route_missing": {
        "zh": "全能者路由缺失",
        "en": "Manager route missing",
    },
    "manager_select_failed": {
        "zh": "全能者决策失败",
        "en": "Manager selection failed",
    },
    "manager_model_missing": {
        "zh": "全能者模型不可用",
        "en": "Manager model missing",
    },
    "dynamic_agent_selected": {
        "zh": "动态专家命中",
        "en": "Dynamic agent selected",
    },
}
_DISPATCH_REASON_LABELS_SETTING_KEY = "AIA_DISPATCH_REASON_LABELS_JSON"
_SPECIALIST_FLAGS_SETTING_KEY = "AIA_CHAT_SPECIALIST_FLAGS_JSON"
_CHAT_SPECIALIST_IDS: tuple[str, ...] = tuple(str(x) for x in SPECIALIST_IDS if str(x).strip())
DEFAULT_TABULAR_SQL_TIMEOUT_MS = 8_000


def _safe_rel_avatar_name(name: str) -> str:
    raw = (name or "").replace("\\", "/").split("/")[-1].strip()
    return raw or "avatar.png"


def _api_lang(store: SqliteStore) -> str:
    v = str(store.get_setting("ui_lang") or "zh").strip().lower()
    return v if v in ("zh", "en") else "zh"


def _init_gateway_executor(
    store: SqliteStore,
    ctx: dict[str, Any],
    *,
    lang: str,
    specialist: str | None,
    policy_session_id: str | None,
) -> Any:
    uid = str(ctx.get("user_id") or "").strip()
    uname = str(ctx.get("username") or "").strip()
    tid = str(ctx.get("tenant_id") or "").strip()
    return build_gateway_executor(
        store,
        lang=lang,
        specialist=specialist,
        profile_id=None,
        openai_api_key=None,
        llm_mode=None,
        model=None,
        base_url=None,
        viewer_user_id=uid or None,
        viewer_username=uname or None,
        viewer_tenant_id=tid or None,
        policy_session_id=policy_session_id,
        path_policy_tenant_id=tid or None,
        path_policy_user_id=uid or None,
    )


def _normalize_attachments_for_api(raw: Any) -> list[dict[str, Any]] | None:
    """DB 存 JSON 字符串；部分历史数据为单对象。统一成 list 便于前端直接使用。"""
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except Exception:
            return None
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        return [raw]
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s or s == "null":
        return None
    try:
        v = json.loads(s)
    except Exception:
        return None
    if isinstance(v, list):
        return [x for x in v if isinstance(x, dict)]
    if isinstance(v, dict):
        return [v]
    return None


def _serialize_message(m: Any) -> dict[str, Any]:
    return {
        "id": int(getattr(m, "id", 0) or 0),
        "session_id": str(getattr(m, "session_id", "") or ""),
        "turn_uuid": str(getattr(m, "turn_uuid", "") or ""),
        "event_type": str(getattr(m, "event_type", "") or ""),
        "event_payload": _safe_json_object(getattr(m, "event_payload", None)),
        "role": str(getattr(m, "role", "") or ""),
        "content": str(getattr(m, "content", "") or ""),
        "tool_calls": getattr(m, "tool_calls", None),
        "attachments": _normalize_attachments_for_api(getattr(m, "attachments", None)),
        "timestamp": str(getattr(m, "timestamp", "") or ""),
    }


def _register_stop(session_id: str) -> threading.Event:
    with _CHAT_STOP_LOCK:
        ev = threading.Event()
        _CHAT_STOP_EVENTS[str(session_id)] = ev
        return ev


def _clear_stop(session_id: str) -> None:
    with _CHAT_STOP_LOCK:
        _CHAT_STOP_EVENTS.pop(str(session_id), None)


def _decode_base64_payload(s: str) -> bytes | None:
    """Decode base64 from browser (may lack padding; URL-safe variants)."""
    raw = (s or "").strip()
    if not raw:
        return None
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1].strip()
    raw = raw.replace("-", "+").replace("_", "/")
    pad = (-len(raw)) % 4
    if pad:
        raw += "=" * pad
    try:
        return base64.b64decode(raw, validate=False)
    except Exception:
        try:
            return base64.standard_b64decode(raw)
        except Exception:
            return None


def _parse_attachments_payload(raw: Any) -> list[dict[str, Any]] | None:
    if not raw:
        return None
    if not isinstance(raw, list):
        return None
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "file").strip() or "file"
        b64 = item.get("data_base64") if "data_base64" in item else item.get("data")
        if not isinstance(b64, str) or not b64.strip():
            continue
        data = _decode_base64_payload(b64)
        if not data:
            continue
        got = process_file_data(name, data)
        if got:
            out.extend(got)
    return out if out else None


def _chat_username(ctx: dict[str, Any]) -> str:
    return str(ctx.get("username") or "").strip().lower()


def _is_administrator_chat_viewer(ctx: dict[str, Any]) -> bool:
    """``administrator`` 账户：在单会话读写/导出等接口上可按租户打开任意会话（供审计与 Session Monitor）。

    ``GET /chat/sessions`` **不再**使用租户全量列表，避免与普通用户会话混在同一侧边栏；
    看全租户会话请用审计页、``GET /admin/api/chat/admin/sessions`` 等专用接口。
    """
    return _chat_username(ctx) == "administrator"


def _require_administrator_chat_viewer(ctx: dict[str, Any]) -> None:
    if not _is_administrator_chat_viewer(ctx):
        raise HTTPException(status_code=403, detail="administrator_only")


def _resolve_chat_session(store: SqliteStore, ctx: dict[str, Any], session_id: str):
    tenant_id = str(ctx.get("tenant_id") or "")
    user_id = str(ctx.get("user_id") or "")
    if _is_administrator_chat_viewer(ctx):
        return store.get_session_in_tenant(session_id=str(session_id or "").strip(), tenant_id=tenant_id)
    return store.get_session_for_user(session_id=session_id, tenant_id=tenant_id, user_id=user_id)


def _effective_user_text(*, text: str, attachments: list[dict[str, Any]] | None, store: SqliteStore) -> str:
    """Streamlit 等价：仅有附件时也要落库一条用户消息，否则模型侧无输入。"""
    t = (text or "").strip()
    if t:
        return t
    if attachments:
        return "（已上传附件）" if _api_lang(store) == "zh" else "(attachment uploaded)"
    return ""


def _safe_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            obj = json.loads(s)
        except Exception:
            return {}
        return obj if isinstance(obj, dict) else {}
    return {}


def _normalize_chat_mode(payload: dict[str, Any] | None) -> tuple[str, str]:
    body = payload or {}
    # Backward compatibility:
    # - chat_mode=composite|specialist
    # - interaction_mode=comprehensive|expert
    raw_interaction = str(body.get("interaction_mode") or "").strip()
    if not raw_interaction:
        legacy_mode = str(body.get("chat_mode") or "").strip().lower()
        if legacy_mode == "specialist":
            raw_interaction = "expert"
        elif legacy_mode == "composite":
            raw_interaction = "comprehensive"
    mode = normalize_interaction_mode(raw_interaction)
    specialist = normalize_requested_specialist(body.get("specialist"))
    return mode, specialist


def _normalize_memory_mode(payload: dict[str, Any] | None) -> str:
    body = payload or {}
    raw = str(body.get("memory_mode") or "").strip().lower()
    return raw if raw in {"default", "store_only"} else "default"


def _specialist_flags_with_overrides(store: SqliteStore) -> dict[str, bool]:
    flags: dict[str, bool] = {sid: True for sid in _CHAT_SPECIALIST_IDS}
    raw = str(store.get_setting(_SPECIALIST_FLAGS_SETTING_KEY) or "").strip()
    if not raw:
        return flags
    try:
        obj = json.loads(raw)
    except Exception:
        return flags
    if not isinstance(obj, dict):
        return flags
    for sid in _CHAT_SPECIALIST_IDS:
        if sid in obj:
            flags[sid] = bool(obj.get(sid))
    # keep generalist always on for safety
    flags["generalist"] = True
    return flags


def _apply_specialist_flags(store: SqliteStore, specialist: str) -> str:
    sid = str(specialist or "generalist").strip().lower() or "generalist"
    flags = _specialist_flags_with_overrides(store)
    if not flags.get(sid, True):
        return "generalist"
    return sid


def _dispatch_reason_label(reason: str, *, lang: str) -> str:
    key = str(reason or "").strip()
    if not key:
        return "-"
    row = _DISPATCH_REASON_LABELS.get(key)
    if not isinstance(row, dict):
        return key
    l = "en" if str(lang or "").startswith("en") else "zh"
    return str(row.get(l) or row.get("en") or key)


def _dispatch_reason_labels_with_overrides(store: SqliteStore) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = dict(_DISPATCH_REASON_LABELS)
    raw = str(store.get_setting(_DISPATCH_REASON_LABELS_SETTING_KEY) or "").strip()
    if not raw:
        return out
    try:
        obj = json.loads(raw)
    except Exception:
        return out
    if not isinstance(obj, dict):
        return out
    for rk, rv in obj.items():
        key = str(rk or "").strip()
        if not key or not isinstance(rv, dict):
            continue
        zh = str(rv.get("zh") or "").strip()
        en = str(rv.get("en") or "").strip()
        if not zh and not en:
            continue
        base = out.get(key, {})
        out[key] = {
            "zh": zh or str(base.get("zh") or ""),
            "en": en or str(base.get("en") or ""),
        }
    return out


def _dispatch_reason_label_from_map(reason: str, *, lang: str, labels: dict[str, dict[str, str]]) -> str:
    key = str(reason or "").strip()
    if not key:
        return "-"
    row = labels.get(key)
    if not isinstance(row, dict):
        return key
    l = "en" if str(lang or "").startswith("en") else "zh"
    return str(row.get(l) or row.get("en") or key)


def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = dict(base or {})
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_dict(dict(out.get(k) or {}), v)
        else:
            out[k] = v
    return out


def _safe_int(raw: Any, default: int, *, min_value: int = 1, max_value: int = 2_000_000) -> int:
    try:
        value = int(raw)
    except Exception:
        return default
    if value < min_value:
        return default
    return min(value, max_value)


def _safe_timeout_ms(raw: Any, default: int = DEFAULT_TABULAR_SQL_TIMEOUT_MS) -> int:
    return _safe_int(raw, default, min_value=100, max_value=120_000)


def _tabular_limits_from_oclaw_config() -> dict[str, int]:
    cfg_path = _oclaw_config_path()
    obj: dict[str, Any] = {}
    try:
        if cfg_path.exists() and cfg_path.is_file():
            loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                obj = loaded
    except Exception:
        obj = {}
    tabular = (
        (((obj.get("plugins") or {}).get("entries") or {}).get("memory-wiki") or {})
        .get("auto", {})
        .get("attachments", {})
        .get("tabular", {})
    )
    if not isinstance(tabular, dict):
        tabular = {}
    return {
        "max_rows_read": _safe_int(tabular.get("max_rows_read"), DEFAULT_TABULAR_ROWS_READ),
        "max_columns": _safe_int(tabular.get("max_columns"), DEFAULT_TABULAR_COLUMNS),
        "max_cell_chars": _safe_int(tabular.get("max_cell_chars"), DEFAULT_TABULAR_CELL_CHARS),
        "max_excel_sheets": _safe_int(tabular.get("max_excel_sheets"), DEFAULT_MAX_EXCEL_SHEETS, max_value=500),
        "large_table_preview_rows": _safe_int(tabular.get("large_table_preview_rows"), 20, max_value=500),
        "tool_mode_enabled": bool(tabular.get("tool_mode_enabled", True)),
        "tool_mode_min_rows": _safe_int(tabular.get("tool_mode_min_rows"), 20_000),
        "tool_mode_max_bytes": _safe_int(tabular.get("tool_mode_max_bytes"), 30 * 1024 * 1024),
        "sql_timeout_ms": _safe_timeout_ms(tabular.get("sql_timeout_ms"), DEFAULT_TABULAR_SQL_TIMEOUT_MS),
    }


def _set_tabular_limits_into_oclaw_config(limits: dict[str, int]) -> dict[str, int]:
    cfg_path = _oclaw_config_path()
    cfg_obj: dict[str, Any] = {}
    try:
        if cfg_path.exists() and cfg_path.is_file():
            loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg_obj = loaded
    except Exception:
        cfg_obj = {}
    patch = {
        "plugins": {
            "entries": {
                "memory-wiki": {
                    "auto": {
                        "attachments": {
                            "tabular": {
                                "max_rows_read": int(limits.get("max_rows_read") or DEFAULT_TABULAR_ROWS_READ),
                                "max_columns": int(limits.get("max_columns") or DEFAULT_TABULAR_COLUMNS),
                                "max_cell_chars": int(limits.get("max_cell_chars") or DEFAULT_TABULAR_CELL_CHARS),
                                "max_excel_sheets": int(limits.get("max_excel_sheets") or DEFAULT_MAX_EXCEL_SHEETS),
                                "large_table_preview_rows": int(limits.get("large_table_preview_rows") or 20),
                                "tool_mode_enabled": bool(limits.get("tool_mode_enabled", True)),
                                "tool_mode_min_rows": int(limits.get("tool_mode_min_rows") or 20_000),
                                "tool_mode_max_bytes": int(limits.get("tool_mode_max_bytes") or (30 * 1024 * 1024)),
                                "sql_timeout_ms": int(
                                    _safe_timeout_ms(limits.get("sql_timeout_ms"), DEFAULT_TABULAR_SQL_TIMEOUT_MS)
                                ),
                            }
                        }
                    }
                }
            }
        }
    }
    merged = _deep_merge_dict(cfg_obj, patch)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    clear_attachment_limits_cache()
    return _tabular_limits_from_oclaw_config()


def _chat_session_mode_setting_key(*, tenant_id: str, user_id: str, session_id: str, field: str) -> str:
    return f"chat.session.mode.{tenant_id}.{user_id}.{session_id}.{field}"


def include_chat_routes(router: APIRouter, *, resolve_auth: Callable[[SqliteStore, str | None], dict[str, Any]]) -> None:
    chat = APIRouter(prefix="/admin/api/chat", tags=["chat"])

    @chat.get("/sessions")
    def api_chat_sessions(
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "")
        user_id = str(ctx.get("user_id") or "")
        # 含 administrator：侧边栏只列「当前登录用户」名下会话，避免租户内他人会话出现在 /chat。
        # 全租户会话列表见审计、GET /admin/api/chat/admin/sessions 等。
        meta = store.get_sessions_list_meta_for_user(tenant_id=tenant_id, user_id=user_id)
        rows = store.list_sessions_for_user(
            tenant_id=tenant_id, user_id=user_id, limit=limit, offset=offset
        )
        return {
            "ok": True,
            "total": int(meta.session_count or 0),
            "sessions": [
                {
                    "id": s.id,
                    "title": s.title,
                    "created_at": s.created_at,
                    "last_message_at": s.last_message_at,
                }
                for s in rows
            ],
        }

    @chat.post("/sessions")
    def api_chat_create_session(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "")
        user_id = str(ctx.get("user_id") or "")
        title = str(payload.get("title") or "").strip() or ("新会话" if _api_lang(store) == "zh" else "New Chat")
        s = store.create_session_for_user(title=title, tenant_id=tenant_id, user_id=user_id)
        return {
            "ok": True,
            "session": {
                "id": s.id,
                "title": s.title,
                "created_at": s.created_at,
                "last_message_at": s.last_message_at,
            },
        }

    @chat.patch("/sessions/{session_id}")
    def api_chat_rename_session(
        session_id: str,
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "")
        user_id = str(ctx.get("user_id") or "")
        sess = _resolve_chat_session(store, ctx, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session_not_found")
        title = str(payload.get("title") or "").strip()[:_SESSION_TITLE_MAX_LEN] or (
            "新会话" if _api_lang(store) == "zh" else "New Chat"
        )
        store.rename_session(session_id, title)
        s = _resolve_chat_session(store, ctx, session_id)
        return {
            "ok": True,
            "session": {
                "id": s.id,
                "title": s.title,
                "created_at": s.created_at,
                "last_message_at": s.last_message_at,
            },
        }

    @chat.delete("/sessions/{session_id}")
    def api_chat_delete_session(
        session_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "")
        user_id = str(ctx.get("user_id") or "")
        sess = _resolve_chat_session(store, ctx, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session_not_found")
        if _is_administrator_chat_viewer(ctx):
            store.delete_session_in_tenant(session_id=session_id, tenant_id=tenant_id)
        else:
            store.delete_session_for_user(session_id=session_id, tenant_id=tenant_id, user_id=user_id)
        remaining = store.list_sessions_for_user(
            tenant_id=tenant_id, user_id=user_id, limit=1, offset=0
        )
        next_id = str(remaining[0].id) if remaining else ""
        if not next_id:
            lang = _api_lang(store)
            ns = store.create_session_for_user(
                title=("新会话" if lang == "zh" else "New Chat"), tenant_id=tenant_id, user_id=user_id
            )
            next_id = str(ns.id)
        return {"ok": True, "next_session_id": next_id}

    @chat.post("/sessions/{session_id}/fork")
    def api_chat_fork_session(
        session_id: str,
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "")
        user_id = str(ctx.get("user_id") or "")
        sess = _resolve_chat_session(store, ctx, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session_not_found")
        last_id = store.get_last_message_id(session_id)
        if last_id is None:
            raise HTTPException(status_code=400, detail="empty_session")
        base_title = (sess.title or "")[:80] or session_id[:8]
        dup_title = str(payload.get("title") or "").strip() or (
            (f"{base_title} (copy)" if _api_lang(store) == "en" else f"{base_title} (副本)")
        )[:_SESSION_TITLE_MAX_LEN]
        try:
            ns = store.fork_session(session_id, last_id, dup_title)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        store.ensure_ui_session_owner(session_id=str(ns.id), tenant_id=tenant_id, user_id=user_id)
        return {
            "ok": True,
            "session": {
                "id": ns.id,
                "title": ns.title,
                "created_at": ns.created_at,
                "last_message_at": ns.last_message_at,
            },
        }

    @chat.get("/sessions/{session_id}/export")
    def api_chat_export_session(
        session_id: str,
        format: str = Query(default="md", description="md or json"),
        authorization: str | None = Header(default=None),
    ) -> Response:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "")
        user_id = str(ctx.get("user_id") or "")
        sess = _resolve_chat_session(store, ctx, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session_not_found")
        fmt = (format or "md").strip().lower()
        if fmt in ("json", "application/json"):
            body = export_session_json(store, session_id)
            return Response(
                content=body.encode("utf-8"),
                media_type="application/json; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="chat-{session_id[:8]}.json"',
                },
            )
        body = export_session_markdown(store, session_id)
        return Response(
            content=body.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="chat-{session_id[:8]}.md"'},
        )

    @chat.get("/sessions/{session_id}/messages")
    def api_chat_messages(
        session_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "")
        user_id = str(ctx.get("user_id") or "")
        sess = _resolve_chat_session(store, ctx, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session_not_found")
        meta = store.get_session_messages_meta(session_id)
        msgs = store.get_messages(session_id=session_id, limit=_CHAT_MSG_LIMIT)
        return {
            "ok": True,
            "message_count": int(meta.message_count or 0),
            "messages": [_serialize_message(m) for m in msgs],
        }

    @chat.get("/sessions/{session_id}/wiki-events")
    def api_chat_wiki_events(
        session_id: str,
        after: str | None = Query(default=None, description="Return events with finished_at > after (ISO)."),
        limit: int = Query(default=20, ge=1, le=200),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_administrator_chat_viewer(ctx)
        tenant_id = str(ctx.get("tenant_id") or "")
        user_id = str(ctx.get("user_id") or "")
        sess = _resolve_chat_session(store, ctx, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session_not_found")
        after_iso = str(after or "").strip()
        rows = store.oclaw_task_list(tenant_id=tenant_id, session_id=str(session_id), limit=max(50, int(limit) * 5))
        events: list[dict[str, Any]] = []
        for t in rows:
            if str(t.task_type or "") != "wiki_capture":
                continue
            if str(t.status or "") not in {"done", "failed"}:
                continue
            fin = str(t.finished_at or "").strip()
            if not fin:
                continue
            if after_iso and fin <= after_iso:
                continue
            try:
                result_obj = json.loads(str(t.result or "{}"))
            except Exception:
                result_obj = {}
            events.append(
                {
                    "task_id": str(t.id),
                    "status": str(t.status),
                    "finished_at": fin,
                    "ok": bool(isinstance(result_obj, dict) and result_obj.get("ok", False)),
                    "result": result_obj if isinstance(result_obj, dict) else {},
                }
            )
        events.sort(key=lambda e: str(e.get("finished_at") or ""))
        return {
            "ok": True,
            "session_id": str(session_id),
            "viewer_user_id": str(user_id),
            "events": events[-max(1, min(int(limit), 200)) :],
        }

    @chat.get("/sessions/{session_id}/wiki-file")
    def api_chat_wiki_file(
        session_id: str,
        path: str = Query(..., description="Relative wiki path, e.g. inbox/merged-turns.md"),
        max_chars: int = Query(default=80_000, ge=1_000, le=200_000),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_administrator_chat_viewer(ctx)
        tenant_id = str(ctx.get("tenant_id") or "")
        _ = str(ctx.get("user_id") or "")
        sess = _resolve_chat_session(store, ctx, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session_not_found")
        wiki_root = _wiki_root_from_config()
        if wiki_root is None:
            raise HTTPException(status_code=404, detail="wiki_root_missing")
        rel = str(path or "").replace("\\", "/").strip().lstrip("/")
        if not rel or ".." in rel.split("/"):
            raise HTTPException(status_code=400, detail="invalid_path")
        fp = (wiki_root / rel).resolve()
        try:
            fp.relative_to(wiki_root.resolve())
        except Exception:
            raise HTTPException(status_code=400, detail="path_outside_wiki_root") from None
        if not fp.exists() or not fp.is_file():
            raise HTTPException(status_code=404, detail="file_not_found")
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            raise HTTPException(status_code=500, detail="read_failed") from None
        return {
            "ok": True,
            "tenant_id": str(tenant_id),
            "session_id": str(session_id),
            "path": rel,
            "truncated": len(content) > int(max_chars),
            "content": content[: int(max_chars)],
        }

    @chat.get("/sessions/{session_id}/mode")
    def api_chat_session_mode_get(
        session_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "")
        user_id = str(ctx.get("user_id") or "")
        sess = _resolve_chat_session(store, ctx, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session_not_found")
        mode_key = _chat_session_mode_setting_key(
            tenant_id=tenant_id, user_id=user_id, session_id=str(session_id), field="interaction_mode"
        )
        specialist_key = _chat_session_mode_setting_key(
            tenant_id=tenant_id, user_id=user_id, session_id=str(session_id), field="specialist"
        )
        memory_mode_key = _chat_session_mode_setting_key(
            tenant_id=tenant_id, user_id=user_id, session_id=str(session_id), field="memory_mode"
        )
        interaction_mode = normalize_interaction_mode(store.get_setting(mode_key))
        specialist = normalize_requested_specialist(store.get_setting(specialist_key))
        specialist = _apply_specialist_flags(store, specialist)
        memory_mode = _normalize_memory_mode({"memory_mode": store.get_setting(memory_mode_key)})
        return {"ok": True, "interaction_mode": interaction_mode, "specialist": specialist, "memory_mode": memory_mode}

    @chat.post("/sessions/{session_id}/mode")
    def api_chat_session_mode_set(
        session_id: str,
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "")
        user_id = str(ctx.get("user_id") or "")
        sess = _resolve_chat_session(store, ctx, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session_not_found")
        interaction_mode = normalize_interaction_mode(payload.get("interaction_mode"))
        specialist = normalize_requested_specialist(payload.get("specialist"))
        specialist = _apply_specialist_flags(store, specialist)
        mode_key = _chat_session_mode_setting_key(
            tenant_id=tenant_id, user_id=user_id, session_id=str(session_id), field="interaction_mode"
        )
        specialist_key = _chat_session_mode_setting_key(
            tenant_id=tenant_id, user_id=user_id, session_id=str(session_id), field="specialist"
        )
        memory_mode_key = _chat_session_mode_setting_key(
            tenant_id=tenant_id, user_id=user_id, session_id=str(session_id), field="memory_mode"
        )
        memory_mode = _normalize_memory_mode(payload)
        store.set_setting(mode_key, interaction_mode)
        store.set_setting(specialist_key, specialist)
        store.set_setting(memory_mode_key, memory_mode)
        return {"ok": True, "interaction_mode": interaction_mode, "specialist": specialist, "memory_mode": memory_mode}

    @chat.get("/admin/user-stats")
    def api_chat_admin_user_stats(
        q: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_administrator_chat_viewer(ctx)
        tenant_id = str(ctx.get("tenant_id") or "")
        total, users, totals = store.list_admin_user_stats(
            tenant_id=tenant_id,
            q=q,
            active_window_minutes=30,
            limit=limit,
            offset=offset,
        )
        return {"ok": True, "total": int(total), "totals": totals, "users": users}

    @chat.get("/admin/sessions")
    def api_chat_admin_sessions(
        user_id: str | None = Query(default=None),
        q: str | None = Query(default=None),
        active_only: bool = Query(default=False),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_administrator_chat_viewer(ctx)
        tenant_id = str(ctx.get("tenant_id") or "")
        total, rows = store.list_admin_sessions(
            tenant_id=tenant_id,
            user_id=user_id,
            q=q,
            active_only=bool(active_only),
            active_window_minutes=30,
            limit=limit,
            offset=offset,
        )
        return {"ok": True, "total": int(total), "sessions": rows}

    @chat.get("/admin/dynamic-expert-stats")
    def api_chat_admin_dynamic_expert_stats(
        limit: int = Query(default=200, ge=20, le=1000),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        lang = _api_lang(store)
        labels = _dispatch_reason_labels_with_overrides(store)
        _require_administrator_chat_viewer(ctx)
        tenant_id = str(ctx.get("tenant_id") or "")
        rows = store.oclaw_task_list(tenant_id=tenant_id, limit=limit)
        total = len(rows)
        dynamic_used = 0
        fallback_generalist = 0
        reasons: dict[str, int] = {}
        specialist_counts: dict[str, int] = {}
        for t in rows:
            payload = _safe_json_object(t.payload)
            if str(payload.get("interaction_mode") or "") != "comprehensive":
                continue
            reason = str(payload.get("dispatch_reason") or "").strip() or "unknown"
            reasons[reason] = int(reasons.get(reason, 0)) + 1
            sel = str(payload.get("manager_selected_specialist") or "generalist").strip() or "generalist"
            specialist_counts[sel] = int(specialist_counts.get(sel, 0)) + 1
            if bool(payload.get("dynamic_agent_used")):
                dynamic_used += 1
            if reason in {"manager_no_specialist_fallback", "dynamic_agent_build_failed"}:
                fallback_generalist += 1
        return {
            "ok": True,
            "window_task_count": int(total),
            "dynamic_used_count": int(dynamic_used),
            "fallback_generalist_count": int(fallback_generalist),
            "dynamic_used_rate": (float(dynamic_used) / float(total)) if total > 0 else 0.0,
            "dispatch_reasons": reasons,
            "dispatch_reason_labels": {k: _dispatch_reason_label_from_map(k, lang=lang, labels=labels) for k in reasons.keys()},
            "selected_specialists": specialist_counts,
        }

    @chat.get("/settings/ui-lang")
    def api_chat_get_ui_lang(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        _ = resolve_auth(store, authorization)
        return {"ok": True, "lang": _api_lang(store)}

    @chat.post("/settings/ui-lang")
    def api_chat_set_ui_lang(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        _ = resolve_auth(store, authorization)
        lang = str(payload.get("lang") or "").strip().lower()
        if lang not in ("zh", "en"):
            raise HTTPException(status_code=400, detail="invalid_lang")
        store.set_setting("ui_lang", lang)
        return {"ok": True, "lang": lang}

    @chat.get("/settings/dispatch-reason-labels")
    def api_chat_get_dispatch_reason_labels(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_administrator_chat_viewer(ctx)
        raw = str(store.get_setting(_DISPATCH_REASON_LABELS_SETTING_KEY) or "").strip()
        overrides: dict[str, Any] = {}
        if raw:
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    overrides = obj
            except Exception:
                overrides = {}
        return {
            "ok": True,
            "setting_key": _DISPATCH_REASON_LABELS_SETTING_KEY,
            "overrides": overrides,
            "effective": _dispatch_reason_labels_with_overrides(store),
        }

    @chat.post("/settings/dispatch-reason-labels")
    def api_chat_set_dispatch_reason_labels(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        body = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_administrator_chat_viewer(ctx)
        overrides = body.get("overrides")
        if overrides is None:
            store.set_setting(_DISPATCH_REASON_LABELS_SETTING_KEY, "")
            return {"ok": True, "cleared": True, "effective": _dispatch_reason_labels_with_overrides(store)}
        if not isinstance(overrides, dict):
            raise HTTPException(status_code=400, detail="invalid_overrides")
        clean: dict[str, dict[str, str]] = {}
        for rk, rv in overrides.items():
            reason = str(rk or "").strip()
            if not reason or not isinstance(rv, dict):
                continue
            zh = str(rv.get("zh") or "").strip()
            en = str(rv.get("en") or "").strip()
            if not zh and not en:
                continue
            clean[reason] = {"zh": zh, "en": en}
        store.set_setting(_DISPATCH_REASON_LABELS_SETTING_KEY, json.dumps(clean, ensure_ascii=False))
        return {"ok": True, "saved": clean, "effective": _dispatch_reason_labels_with_overrides(store)}

    @chat.get("/settings/specialist-flags")
    def api_chat_get_specialist_flags(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_administrator_chat_viewer(ctx)
        flags = _specialist_flags_with_overrides(store)
        available = [sid for sid in _CHAT_SPECIALIST_IDS if bool(flags.get(sid, True))]
        return {
            "ok": True,
            "setting_key": _SPECIALIST_FLAGS_SETTING_KEY,
            "flags": flags,
            "available_specialists": available,
        }

    @chat.post("/settings/specialist-flags")
    def api_chat_set_specialist_flags(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        body = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_administrator_chat_viewer(ctx)
        raw_flags = body.get("flags")
        if raw_flags is None:
            store.set_setting(_SPECIALIST_FLAGS_SETTING_KEY, "")
            flags = _specialist_flags_with_overrides(store)
            return {"ok": True, "cleared": True, "flags": flags}
        if not isinstance(raw_flags, dict):
            raise HTTPException(status_code=400, detail="invalid_flags")
        clean: dict[str, bool] = {}
        for sid in _CHAT_SPECIALIST_IDS:
            if sid in raw_flags:
                clean[sid] = bool(raw_flags.get(sid))
        clean["generalist"] = True
        store.set_setting(_SPECIALIST_FLAGS_SETTING_KEY, json.dumps(clean, ensure_ascii=False))
        flags = _specialist_flags_with_overrides(store)
        return {"ok": True, "saved": clean, "flags": flags}

    @chat.get("/settings/attachment-limits")
    def api_chat_get_attachment_limits(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_administrator_chat_viewer(ctx)
        limits = _tabular_limits_from_oclaw_config()
        return {"ok": True, "limits": limits}

    @chat.post("/settings/attachment-limits")
    def api_chat_set_attachment_limits(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        body = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_administrator_chat_viewer(ctx)
        raw = body.get("limits")
        if raw is None:
            limits = {
                "max_rows_read": DEFAULT_TABULAR_ROWS_READ,
                "max_columns": DEFAULT_TABULAR_COLUMNS,
                "max_cell_chars": DEFAULT_TABULAR_CELL_CHARS,
                "max_excel_sheets": DEFAULT_MAX_EXCEL_SHEETS,
                "large_table_preview_rows": 20,
                "tool_mode_enabled": True,
                "tool_mode_min_rows": 20_000,
                "tool_mode_max_bytes": 30 * 1024 * 1024,
                "sql_timeout_ms": DEFAULT_TABULAR_SQL_TIMEOUT_MS,
            }
            saved = _set_tabular_limits_into_oclaw_config(limits)
            return {"ok": True, "cleared": True, "limits": saved}
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail="invalid_limits")
        next_limits = {
            "max_rows_read": _safe_int(raw.get("max_rows_read"), DEFAULT_TABULAR_ROWS_READ),
            "max_columns": _safe_int(raw.get("max_columns"), DEFAULT_TABULAR_COLUMNS),
            "max_cell_chars": _safe_int(raw.get("max_cell_chars"), DEFAULT_TABULAR_CELL_CHARS),
            "max_excel_sheets": _safe_int(raw.get("max_excel_sheets"), DEFAULT_MAX_EXCEL_SHEETS, max_value=500),
            "large_table_preview_rows": _safe_int(raw.get("large_table_preview_rows"), 20, max_value=500),
            "tool_mode_enabled": bool(raw.get("tool_mode_enabled", True)),
            "tool_mode_min_rows": _safe_int(raw.get("tool_mode_min_rows"), 20_000),
            "tool_mode_max_bytes": _safe_int(raw.get("tool_mode_max_bytes"), 30 * 1024 * 1024),
            "sql_timeout_ms": _safe_timeout_ms(raw.get("sql_timeout_ms"), DEFAULT_TABULAR_SQL_TIMEOUT_MS),
        }
        saved = _set_tabular_limits_into_oclaw_config(next_limits)
        return {"ok": True, "limits": saved}

    @chat.get("/profile")
    def api_chat_profile_get(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "").strip()
        user_id = str(ctx.get("user_id") or "").strip()
        if not tenant_id or not user_id:
            raise HTTPException(status_code=401, detail="auth_required")
        row = store.get_user_by_id(tenant_id=tenant_id, user_id=user_id)
        if not row:
            raise HTTPException(status_code=404, detail="user_not_found")
        aid = str(row.get("avatar_attachment_id") or "").strip()
        avatar_url = f"/admin/api/chat/attachments/{aid}" if aid else ""
        return {
            "ok": True,
            "profile": {
                "id": str(row.get("id") or ""),
                "tenant_id": str(row.get("tenant_id") or ""),
                "username": str(row.get("username") or ""),
                "display_name": str(row.get("display_name") or ""),
                "role": str(row.get("role") or ""),
                "is_active": bool(row.get("is_active")),
                "created_at": str(row.get("created_at") or ""),
                "avatar_attachment_id": aid or None,
                "avatar_url": avatar_url or None,
            },
        }

    @chat.patch("/profile")
    def api_chat_profile_patch(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "").strip()
        user_id = str(ctx.get("user_id") or "").strip()
        if not tenant_id or not user_id:
            raise HTTPException(status_code=401, detail="auth_required")
        if "display_name" in payload:
            dn = str(payload.get("display_name") or "").strip()[:120] or str(ctx.get("username") or "User").strip() or "User"
            store.update_user_account(tenant_id=tenant_id, user_id=user_id, display_name=dn)
        row = store.get_user_by_id(tenant_id=tenant_id, user_id=user_id) or {}
        aid = str(row.get("avatar_attachment_id") or "").strip()
        return {
            "ok": True,
            "profile": {
                "id": str(row.get("id") or ""),
                "tenant_id": str(row.get("tenant_id") or ""),
                "username": str(row.get("username") or ""),
                "display_name": str(row.get("display_name") or ""),
                "role": str(row.get("role") or ""),
                "is_active": bool(row.get("is_active")),
                "created_at": str(row.get("created_at") or ""),
                "avatar_attachment_id": aid or None,
                "avatar_url": (f"/admin/api/chat/attachments/{aid}" if aid else None),
            },
        }

    @chat.post("/profile/avatar")
    async def api_chat_profile_avatar_upload(
        authorization: str | None = Header(default=None),
        file: UploadFile = File(...),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "").strip()
        user_id = str(ctx.get("user_id") or "").strip()
        if not tenant_id or not user_id:
            raise HTTPException(status_code=401, detail="auth_required")
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="empty_file")
        if len(raw) > _AVATAR_UPLOAD_MAX_BYTES:
            raise HTTPException(status_code=413, detail="avatar_too_large")
        mime = (str(file.content_type or "").split(";", 1)[0]).strip().lower()
        if mime == "image/jpg":
            mime = "image/jpeg"
        if mime not in _AVATAR_MIMES:
            raise HTTPException(status_code=415, detail="avatar_invalid_mime")
        fname = _safe_rel_avatar_name(str(file.filename or "avatar"))
        ast = AttachmentAssetStore()
        meta = ast.save_bytes(raw, filename=fname, mime=mime)
        aid = str(meta.attachment_id or "").strip()
        if not aid:
            raise HTTPException(status_code=500, detail="avatar_save_failed")
        store.update_user_account(tenant_id=tenant_id, user_id=user_id, avatar_attachment_id=aid)
        return {
            "ok": True,
            "avatar_attachment_id": aid,
            "avatar_url": f"/admin/api/chat/attachments/{aid}",
        }

    @chat.delete("/profile/avatar")
    def api_chat_profile_avatar_delete(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "").strip()
        user_id = str(ctx.get("user_id") or "").strip()
        if not tenant_id or not user_id:
            raise HTTPException(status_code=401, detail="auth_required")
        store.update_user_account(tenant_id=tenant_id, user_id=user_id, avatar_attachment_id="")
        return {"ok": True, "avatar_attachment_id": None, "avatar_url": None}

    @chat.post("/sessions/{session_id}/stop")
    def api_chat_stop_turn(
        session_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        sess = _resolve_chat_session(store, ctx, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session_not_found")
        sid = str(session_id)
        with _CHAT_STOP_LOCK:
            ev = _CHAT_STOP_EVENTS.get(sid)
        if ev:
            ev.set()
        return {"ok": True}

    @chat.get("/attachments/{attachment_id}")
    def api_chat_attachment_bytes(
        attachment_id: str,
        authorization: str | None = Header(default=None),
    ) -> Response:
        store = SqliteStore(db_path())
        _ = resolve_auth(store, authorization)
        aid = str(attachment_id or "").strip()
        if not aid:
            raise HTTPException(status_code=400, detail="attachment_id_required")
        ast = AttachmentAssetStore()
        try:
            blob, meta = ast.load_bytes(aid)
        except Exception:
            raise HTTPException(status_code=404, detail="attachment_not_found") from None
        mime = (meta.mime if meta else None) or "application/octet-stream"
        return Response(content=blob, media_type=mime)

    @chat.post("/sessions/{session_id}/messages")
    def api_chat_send(
        session_id: str,
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "")
        user_id = str(ctx.get("user_id") or "")
        role = str(ctx.get("role") or "member")
        sess = _resolve_chat_session(store, ctx, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session_not_found")
        text_raw = str(payload.get("text") or "").strip()
        idempotency_key = str(payload.get("idempotency_key") or payload.get("idempotencyKey") or "").strip()
        attachments = _parse_attachments_payload(payload.get("attachments"))
        interaction_mode, selected_specialist = _normalize_chat_mode(payload)
        memory_mode = _normalize_memory_mode(payload)
        if "interaction_mode" not in payload and "chat_mode" not in payload:
            mode_key = _chat_session_mode_setting_key(
                tenant_id=tenant_id, user_id=user_id, session_id=str(session_id), field="interaction_mode"
            )
            interaction_mode = normalize_interaction_mode(store.get_setting(mode_key))
        if "specialist" not in payload:
            specialist_key = _chat_session_mode_setting_key(
                tenant_id=tenant_id, user_id=user_id, session_id=str(session_id), field="specialist"
            )
            selected_specialist = normalize_requested_specialist(store.get_setting(specialist_key))
        if "memory_mode" not in payload:
            memory_mode_key = _chat_session_mode_setting_key(
                tenant_id=tenant_id, user_id=user_id, session_id=str(session_id), field="memory_mode"
            )
            memory_mode = _normalize_memory_mode({"memory_mode": store.get_setting(memory_mode_key)})
        selected_specialist = _apply_specialist_flags(store, selected_specialist)
        if not text_raw and not attachments:
            raise HTTPException(status_code=400, detail="text_or_attachments_required")
        text = _effective_user_text(text=text_raw, attachments=attachments, store=store)
        if not _is_administrator_chat_viewer(ctx) and tenant_id and user_id:
            store.ensure_ui_session_owner(session_id=session_id, tenant_id=tenant_id, user_id=user_id)
        lang = _api_lang(store)
        apply_gateway_mcp_env_to_os()
        manager_agent = _init_gateway_executor(
            store,
            ctx,
            lang=lang,
            specialist="generalist",
            policy_session_id=str(session_id),
        )
        specialist_factory = lambda sid: _init_gateway_executor(
            store,
            ctx,
            lang=lang,
            specialist=sid,
            policy_session_id=str(session_id),
        )
        try:
            gw = OclawGateway(store=store)
            msg = StandardMessage(
                session_id=str(session_id),
                tenant_id=tenant_id,
                user_id=user_id,
                role=role,
                channel="admin_chat",
                text=str(text or ""),
                attachments=list(attachments or []),
                metadata={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "role": role,
                    "channel": "admin_chat",
                    "interaction_mode": interaction_mode,
                    "selected_specialist": selected_specialist,
                    "memory_mode": memory_mode,
                },
            )
            gw_result = gw.handle_turn(
                msg=msg,
                lang=lang,
                executor=manager_agent,
                run_id=(idempotency_key or None),
                specialist_executor_factory=specialist_factory,
            )
            reply = gw_result.reply_text
        except GenerationInterrupted:
            msg = "已中断回答。" if lang == "zh" else "Response stopped."
            store.add_message(session_id=session_id, role="assistant", content=msg)
            return {"ok": True, "reply": msg, "interrupted": True}
        return {
            "ok": True,
            "reply": str(reply or ""),
            "mode": str(getattr(gw_result, "mode", "sync_direct") or "sync_direct"),
            "task_id": str(getattr(gw_result, "task_id", "") or ""),
            "interaction_mode": str(getattr(gw_result, "interaction_mode", interaction_mode) or interaction_mode),
            "selected_specialist": str(getattr(gw_result, "selected_specialist", selected_specialist) or selected_specialist),
        }

    @chat.post("/sessions/{session_id}/messages/stream")
    def api_chat_send_stream(
        session_id: str,
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> StreamingResponse:
        """Server-Sent Events: token deltas + progress + tool_ui, then done (assistant persisted by run_turn)."""
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        tenant_id = str(ctx.get("tenant_id") or "")
        user_id = str(ctx.get("user_id") or "")
        role = str(ctx.get("role") or "member")
        sess = _resolve_chat_session(store, ctx, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session_not_found")
        text_raw = str(payload.get("text") or "").strip()
        attachments = _parse_attachments_payload(payload.get("attachments"))
        interaction_mode, selected_specialist = _normalize_chat_mode(payload)
        memory_mode = _normalize_memory_mode(payload)
        if "interaction_mode" not in payload and "chat_mode" not in payload:
            mode_key = _chat_session_mode_setting_key(
                tenant_id=tenant_id, user_id=user_id, session_id=str(session_id), field="interaction_mode"
            )
            interaction_mode = normalize_interaction_mode(store.get_setting(mode_key))
        if "specialist" not in payload:
            specialist_key = _chat_session_mode_setting_key(
                tenant_id=tenant_id, user_id=user_id, session_id=str(session_id), field="specialist"
            )
            selected_specialist = normalize_requested_specialist(store.get_setting(specialist_key))
        if "memory_mode" not in payload:
            memory_mode_key = _chat_session_mode_setting_key(
                tenant_id=tenant_id, user_id=user_id, session_id=str(session_id), field="memory_mode"
            )
            memory_mode = _normalize_memory_mode({"memory_mode": store.get_setting(memory_mode_key)})
        selected_specialist = _apply_specialist_flags(store, selected_specialist)
        if not text_raw and not attachments:
            raise HTTPException(status_code=400, detail="text_or_attachments_required")
        text = _effective_user_text(text=text_raw, attachments=attachments, store=store)
        if not _is_administrator_chat_viewer(ctx) and tenant_id and user_id:
            store.ensure_ui_session_owner(session_id=session_id, tenant_id=tenant_id, user_id=user_id)
        lang = _api_lang(store)
        apply_gateway_mcp_env_to_os()
        manager_agent = _init_gateway_executor(
            store,
            ctx,
            lang=lang,
            specialist="generalist",
            policy_session_id=str(session_id),
        )
        specialist_factory = lambda sid: _init_gateway_executor(
            store,
            ctx,
            lang=lang,
            specialist=sid,
            policy_session_id=str(session_id),
        )
        meta = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": role,
            "channel": "admin_chat",
            "interaction_mode": interaction_mode,
            "selected_specialist": selected_specialist,
            "memory_mode": memory_mode,
        }

        _DONE = object()
        max_q = str(store.get_setting("AIA_SSE_QUEUE_MAXSIZE") or "").strip()
        if not max_q:
            max_q = str(os.getenv("AIA_SSE_QUEUE_MAXSIZE") or "").strip()
        q_maxsize = 2000
        if max_q.isdigit():
            q_maxsize = max(200, min(int(max_q), 50_000))
        q: queue.Queue[tuple[str, Any] | object] = queue.Queue(maxsize=q_maxsize)
        sid = str(session_id)
        stop_ev = _register_stop(sid)
        dropped = {"count": 0}

        def _emit(kind: str, data: Any) -> None:
            item = (kind, data)
            try:
                q.put_nowait(item)
                return
            except Exception:
                pass
            # Backpressure: if queue is full, drop low-priority events.
            if kind in ("token", "progress", "tool_ui"):
                dropped["count"] += 1
                return
            # Always try to deliver terminal events.
            q.put(item)

        def _worker() -> None:
            try:

                def should_stop() -> bool:
                    return stop_ev.is_set()

                def on_tool_ui(event: str, pl: dict[str, Any]) -> None:
                    ev_name = str(event or "")
                    kind = "skill_ui" if ev_name.startswith("skill_") else "tool_ui"
                    _emit(kind, {"event": ev_name, "payload": pl})

                gw = OclawGateway(store=store)
                msg = StandardMessage(
                    session_id=str(session_id),
                    tenant_id=tenant_id,
                    user_id=user_id,
                    role=role,
                    channel="admin_chat",
                    text=str(text or ""),
                    attachments=list(attachments or []),
                    metadata=dict(meta),
                )
                gw_result = gw.handle_turn(
                    msg=msg,
                    lang=lang,
                    executor=manager_agent,
                    specialist_executor_factory=specialist_factory,
                    on_token=lambda s: _emit("token", s),
                    on_progress=lambda s: _emit("progress", s),
                    on_tool_ui=on_tool_ui,
                    should_stop=should_stop,
                )
                reply = gw_result.reply_text
                _emit(
                    "done",
                    {
                        "reply": str(reply or ""),
                        "mode": str(getattr(gw_result, "mode", "sync_direct") or "sync_direct"),
                        "task_id": str(getattr(gw_result, "task_id", "") or ""),
                        "interaction_mode": str(
                            getattr(gw_result, "interaction_mode", interaction_mode) or interaction_mode
                        ),
                        "selected_specialist": str(
                            getattr(gw_result, "selected_specialist", selected_specialist) or selected_specialist
                        ),
                    },
                )
            except GenerationInterrupted:
                msg = "已中断回答。" if lang == "zh" else "Response stopped."
                try:
                    store.add_message(session_id=session_id, role="assistant", content=msg)
                except Exception:
                    pass
                _emit("done", {"reply": msg, "interrupted": True})
            except Exception as e:
                _emit("error", str(e))
            finally:
                _clear_stop(sid)
                q.put(_DONE)

        threading.Thread(target=_worker, name="chat_stream", daemon=True).start()

        def event_iter() -> Iterator[str]:
            while True:
                item = q.get()
                if item is _DONE:
                    break
                kind, data = item  # type: ignore[misc]
                if kind == "token":
                    line = json.dumps({"type": "token", "delta": data}, ensure_ascii=False)
                elif kind == "progress":
                    line = json.dumps({"type": "progress", "message": data}, ensure_ascii=False)
                elif kind == "tool_ui":
                    line = json.dumps({"type": "tool_ui", **(data if isinstance(data, dict) else {})}, ensure_ascii=False)
                elif kind == "skill_ui":
                    line = json.dumps({"type": "skill_ui", **(data if isinstance(data, dict) else {})}, ensure_ascii=False)
                elif kind == "done":
                    line = json.dumps(
                        {
                            "type": "done",
                            "reply": (data or {}).get("reply", ""),
                            "interrupted": bool((data or {}).get("interrupted")),
                            "mode": str((data or {}).get("mode") or "sync_direct"),
                            "task_id": str((data or {}).get("task_id") or ""),
                            "interaction_mode": str((data or {}).get("interaction_mode") or interaction_mode),
                            "selected_specialist": str((data or {}).get("selected_specialist") or selected_specialist),
                            "dropped_events": int(dropped["count"] or 0),
                        },
                        ensure_ascii=False,
                    )
                elif kind == "error":
                    line = json.dumps({"type": "error", "message": str(data)}, ensure_ascii=False)
                else:
                    continue
                yield f"data: {line}\n\n"

        return StreamingResponse(
            event_iter(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    router.include_router(chat)


__all__ = ["include_chat_routes"]
