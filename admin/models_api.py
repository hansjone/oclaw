"""Admin API: LLM profiles, agent bindings, UI language, eval (parity with Streamlit settings)."""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query
from fastapi.responses import Response

from oclaw.agents.factory import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL
from oclaw.agents.specialists import (
    AGENT_PROFILE_BINDINGS_KEY,
    AGENT_ROLE_IDS,
    dump_agent_profile_bindings,
    parse_agent_profile_bindings,
)
from oclaw.platform.config.paths import db_path
from oclaw.orchestration.evaluation import eval_summary
from oclaw.platform.persistence.sqlite_store import (
    LLM_BUILTIN_OLLAMA_PROFILE_ID,
    SqliteStore,
    active_llm_profile_setting_key,
    agent_profile_bindings_setting_key,
    is_administrator_model_pool,
)

_LLM_MODE_OPTIONS = frozenset({"openai", "openai_responses", "anthropic", "google", "ollama", "rule"})
_LLM_USER_CREATE_MODES = frozenset({"openai", "anthropic", "google", "ollama", "rule"})


def _require_permission(ctx: dict[str, Any], permission: str) -> None:
    perms = set(str(x) for x in (ctx.get("permissions") or []))
    if permission in perms:
        return
    if str(ctx.get("role") or "") == "owner":
        return
    raise HTTPException(status_code=403, detail=f"forbidden:{permission}")


def _require_models_mutate(ctx: dict[str, Any]) -> None:
    """administrator 编辑全局池需 tenant:write；其余用户编辑自己的复制池仅需 read。"""
    uname = str(ctx.get("username") or "").strip()
    if is_administrator_model_pool(uname):
        _require_permission(ctx, "admin:tenant:write")
    else:
        _require_permission(ctx, "admin:read")


def _models_list_kwargs(ctx: dict[str, Any]) -> dict[str, Any]:
    uid = str(ctx.get("user_id") or "").strip()
    uname = str(ctx.get("username") or "").strip()
    tid = str(ctx.get("tenant_id") or "").strip()
    if not uid:
        return {}
    out: dict[str, Any] = {"viewer_user_id": uid, "viewer_username": uname or None}
    if tid:
        out["viewer_tenant_id"] = tid
    return out


def _active_key(ctx: dict[str, Any]) -> str:
    uid = str(ctx.get("user_id") or "").strip()
    uname = str(ctx.get("username") or "").strip()
    if not uid:
        return "active_llm_profile_id"
    return active_llm_profile_setting_key(uid, uname or None)


def _bindings_key(ctx: dict[str, Any]) -> str:
    uid = str(ctx.get("user_id") or "").strip()
    uname = str(ctx.get("username") or "").strip()
    if not uid:
        return AGENT_PROFILE_BINDINGS_KEY
    return agent_profile_bindings_setting_key(uid, uname or None)


def _assert_profile_mutable(ctx: dict[str, Any], prof: dict[str, Any] | None) -> dict[str, Any]:
    if not prof:
        raise HTTPException(status_code=404, detail="profile_not_found")
    if prof.get("is_builtin"):
        return prof
    own = str(prof.get("owner_user_id") or "").strip()
    uid = str(ctx.get("user_id") or "").strip()
    uname = str(ctx.get("username") or "").strip()
    if is_administrator_model_pool(uname):
        return prof
    if own == uid:
        return prof
    raise HTTPException(status_code=403, detail="profile_forbidden")


def _can_manage_llm_grants(ctx: dict[str, Any]) -> bool:
    uname = str(ctx.get("username") or "").strip()
    if not is_administrator_model_pool(uname):
        return False
    perms = set(str(x) for x in (ctx.get("permissions") or []))
    if "admin:tenant:write" in perms:
        return True
    return str(ctx.get("role") or "") == "owner"


def _require_grant_manager(ctx: dict[str, Any]) -> None:
    if not _can_manage_llm_grants(ctx):
        raise HTTPException(status_code=403, detail="grants_administrator_only")


def _profile_shareable_for_admin_grant(ctx: dict[str, Any], prof: dict[str, Any] | None) -> bool:
    """仅全局池（无 owner）或操作者本人名下的 profile 可被授权给团队/用户。"""
    if not prof or prof.get("is_builtin"):
        return False
    own = str(prof.get("owner_user_id") or "").strip()
    uid = str(ctx.get("user_id") or "").strip()
    if not own:
        return True
    return bool(uid) and own == uid


def _normalize_active(
    store: SqliteStore, profiles: list[dict[str, Any]], profile_ids: list[str], ctx: dict[str, Any]
) -> str:
    if not profile_ids:
        return ""
    key = _active_key(ctx)
    active_id = str(store.get_setting(key) or "").strip()
    if active_id not in profile_ids:
        store.set_setting(key, LLM_BUILTIN_OLLAMA_PROFILE_ID)
        active_id = LLM_BUILTIN_OLLAMA_PROFILE_ID
    if active_id not in profile_ids:
        active_id = profile_ids[0]
        store.set_setting(key, active_id)
    return active_id


def include_model_mgmt_routes(
    router: APIRouter,
    *,
    resolve_auth: Callable[[SqliteStore, str | None], dict[str, Any]],
) -> None:
    mg = APIRouter(prefix="/admin/api/models", tags=["models"])

    @mg.get("")
    def api_models_state(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        uid = str(ctx.get("user_id") or "").strip()
        uname = str(ctx.get("username") or "").strip()
        lk = _models_list_kwargs(ctx)
        profiles = store.list_llm_profiles(visible_only=True, **lk)
        profile_ids = [str(p["id"]) for p in profiles]
        active_id = _normalize_active(store, profiles, profile_ids, ctx)
        bindings = parse_agent_profile_bindings(store.get_setting(_bindings_key(ctx)))
        ui_lang = str(store.get_setting("ui_lang") or "zh").strip().lower()
        if ui_lang not in ("zh", "en"):
            ui_lang = "zh"
        secret = ""
        if active_id and active_id in profile_ids:
            active_prof = next((p for p in profiles if str(p.get("id") or "") == active_id), None)
            if is_administrator_model_pool(uname) or (active_prof and active_prof.get("mutable", True)):
                secret = store.get_llm_profile_secret(active_id) or ""
        out: dict[str, Any] = {
            "ok": True,
            "active_llm_profile_id": active_id,
            "profiles": profiles,
            "bindings": bindings,
            "ui_lang": ui_lang,
            "builtin_ollama_profile_id": LLM_BUILTIN_OLLAMA_PROFILE_ID,
            "has_openai_api_key_env": bool((os.getenv("OPENAI_API_KEY") or "").strip()),
            "role_ids": list(AGENT_ROLE_IDS),
            "profile_secret": secret,
            "can_manage_llm_grants": _can_manage_llm_grants(ctx),
            # 便于核对「浏览器连的是哪台网关、网关读的是哪个库文件」
            "db_path": db_path(),
        }
        return out

    @mg.post("/active")
    def api_models_set_active(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        # 与能进入控制台一致：切换「当前选用」不写密钥，仅需读权限即可。
        _require_permission(ctx, "admin:read")
        profiles = store.list_llm_profiles(visible_only=True, **_models_list_kwargs(ctx))
        profile_ids = [str(p["id"]) for p in profiles]
        pid = str(payload.get("profile_id") or "").strip()
        if pid not in profile_ids:
            raise HTTPException(status_code=400, detail="invalid_profile_id")
        store.set_setting(_active_key(ctx), pid)
        return {"ok": True, "active_llm_profile_id": pid}

    @mg.post("/bindings")
    def api_models_set_bindings(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_models_mutate(ctx)
        profiles = store.list_llm_profiles(visible_only=True, **_models_list_kwargs(ctx))
        profile_ids = set(str(p["id"]) for p in profiles)
        raw = payload.get("bindings")
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail="bindings_object_required")
        cur = parse_agent_profile_bindings(store.get_setting(_bindings_key(ctx)))
        for rid in AGENT_ROLE_IDS:
            v = raw.get(rid)
            if v is None:
                continue
            s = str(v).strip()
            if s and s not in profile_ids:
                raise HTTPException(status_code=400, detail=f"invalid_binding:{rid}")
            cur[rid] = s
        store.set_setting(_bindings_key(ctx), dump_agent_profile_bindings(cur))
        return {"ok": True, "bindings": cur}

    @mg.post("/profiles")
    def api_models_create_profile(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_models_mutate(ctx)
        name = str(payload.get("name") or "").strip() or "新配置"
        mode = str(payload.get("mode") or "openai").strip().lower()
        if mode not in _LLM_USER_CREATE_MODES:
            raise HTTPException(status_code=400, detail="invalid_mode")
        if mode == "openai":
            new_model = "gpt-4o-mini"
            new_bu = ""
        else:
            new_model = DEFAULT_OLLAMA_MODEL
            new_bu = DEFAULT_OLLAMA_BASE_URL
        own: str | None = None
        uid = str(ctx.get("user_id") or "").strip()
        uname = str(ctx.get("username") or "").strip()
        if uid and not is_administrator_model_pool(uname):
            own = uid
        pid = store.create_llm_profile(name=name, mode=mode, model=new_model, base_url=new_bu or None, owner_user_id=own)
        store.set_setting(_active_key(ctx), pid)
        prof = store.get_llm_profile(pid)
        return {"ok": True, "profile_id": pid, "profile": prof}

    @mg.patch("/profiles/{profile_id}")
    def api_models_patch_profile(
        profile_id: str,
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_models_mutate(ctx)
        pid = str(profile_id or "").strip()
        prof = _assert_profile_mutable(ctx, store.get_llm_profile(pid))
        name = str(payload.get("name") if payload.get("name") is not None else prof.get("name") or "").strip() or "未命名"
        mode_raw = str(payload.get("mode") if payload.get("mode") is not None else prof.get("mode") or "openai").strip().lower()
        if pid == LLM_BUILTIN_OLLAMA_PROFILE_ID:
            mode_save = "ollama"
        else:
            if mode_raw not in _LLM_MODE_OPTIONS:
                raise HTTPException(status_code=400, detail="invalid_mode")
            mode_save = mode_raw
        model = payload.get("model")
        base_url = payload.get("base_url")
        model_s = str(model).strip() if model is not None else str(prof.get("model") or "").strip()
        bu_s = str(base_url).strip() if base_url is not None else str(prof.get("base_url") or "").strip()
        store.update_llm_profile(
            profile_id=pid,
            name=name,
            mode=mode_save,
            model=model_s or None,
            base_url=bu_s or None,
        )
        store.set_setting(_active_key(ctx), pid)
        return {"ok": True, "profile": store.get_llm_profile(pid)}

    @mg.post("/profiles/{profile_id}/secret")
    def api_models_profile_secret(
        profile_id: str,
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_models_mutate(ctx)
        pid = str(profile_id or "").strip()
        prof = _assert_profile_mutable(ctx, store.get_llm_profile(pid))
        remember = bool(payload.get("remember"))
        key_text = str(payload.get("secret") or "").strip()
        mode_save = str(prof.get("mode") or "openai").strip().lower()
        if pid == LLM_BUILTIN_OLLAMA_PROFILE_ID:
            mode_save = "ollama"
        if mode_save in ("openai", "ollama"):
            if remember:
                if key_text:
                    store.set_llm_profile_secret(pid, key_text)
                elif mode_save == "openai":
                    raise HTTPException(status_code=400, detail="remember_key_empty")
                else:
                    store.clear_llm_profile_secret(pid)
            else:
                store.clear_llm_profile_secret(pid)
        return {"ok": True, "profile": store.get_llm_profile(pid)}

    @mg.delete("/profiles/{profile_id}")
    def api_models_delete_profile(
        profile_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_models_mutate(ctx)
        pid = str(profile_id or "").strip()
        _assert_profile_mutable(ctx, store.get_llm_profile(pid))
        try:
            store.delete_llm_profile(pid)
        except ValueError:
            raise HTTPException(status_code=400, detail="cannot_delete_builtin")
        remaining = store.list_llm_profiles(visible_only=True, **_models_list_kwargs(ctx))
        new_active = remaining[0]["id"] if remaining else LLM_BUILTIN_OLLAMA_PROFILE_ID
        store.set_setting(_active_key(ctx), new_active)
        return {"ok": True, "active_llm_profile_id": new_active}

    @mg.get("/members")
    def api_models_members(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_grant_manager(ctx)
        tid = str(ctx.get("tenant_id") or "").strip()
        if not tid:
            raise HTTPException(status_code=400, detail="tenant_required")
        users = store.list_users(tenant_id=tid, limit=500, offset=0, include_inactive=True)
        members: list[dict[str, Any]] = []
        for u in users:
            mid = str(u.get("id") or "").strip()
            un = str(u.get("username") or "").strip()
            if not mid:
                continue
            profs = store.list_llm_profiles(
                visible_only=True,
                viewer_user_id=mid,
                viewer_username=un or None,
                viewer_tenant_id=tid,
            )
            members.append(
                {
                    "user_id": mid,
                    "username": un,
                    "display_name": str(u.get("display_name") or "").strip(),
                    "role": str(u.get("role") or "").strip(),
                    "profiles": profs,
                }
            )
        return {"ok": True, "members": members}

    @mg.get("/grants/tenant")
    def api_models_grants_tenant_get(
        profile_id: str = Query(...),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_grant_manager(ctx)
        tid = str(ctx.get("tenant_id") or "").strip()
        pid = str(profile_id or "").strip()
        if not tid or not pid:
            raise HTTPException(status_code=400, detail="tenant_or_profile_required")
        granted = store.tenant_has_llm_profile_grant(tid, pid)
        return {"ok": True, "granted": granted}

    @mg.post("/grants/tenant")
    def api_models_grants_tenant_create(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_grant_manager(ctx)
        tid = str(ctx.get("tenant_id") or "").strip()
        pid = str(payload.get("profile_id") or "").strip()
        if not tid or not pid:
            raise HTTPException(status_code=400, detail="profile_id_required")
        prof = store.get_llm_profile(pid)
        if not _profile_shareable_for_admin_grant(ctx, prof):
            raise HTTPException(status_code=403, detail="profile_not_shareable")
        actor = str(ctx.get("user_id") or "").strip() or None
        try:
            gid = store.grant_llm_profile_to_tenant(
                tenant_id=tid, profile_id=pid, created_by_user_id=actor
            )
        except ValueError as e:
            code = str(e)
            if code == "profile_not_found":
                raise HTTPException(status_code=404, detail=code) from e
            raise HTTPException(status_code=400, detail=code) from e
        return {"ok": True, "grant_id": gid}

    @mg.delete("/grants/tenant")
    def api_models_grants_tenant_revoke(
        profile_id: str = Query(...),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_grant_manager(ctx)
        tid = str(ctx.get("tenant_id") or "").strip()
        pid = str(profile_id or "").strip()
        if not tid or not pid:
            raise HTTPException(status_code=400, detail="profile_id_required")
        n = store.revoke_llm_profile_tenant_grant(tenant_id=tid, profile_id=pid)
        return {"ok": True, "removed": int(n)}

    @mg.get("/grants")
    def api_models_grants_list(
        profile_id: str = Query(..., description="llm_profile id"),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_grant_manager(ctx)
        tid = str(ctx.get("tenant_id") or "").strip()
        pid = str(profile_id or "").strip()
        if not tid or not pid:
            raise HTTPException(status_code=400, detail="tenant_or_profile_required")
        rows = store.list_llm_profile_grants_for_profile(tid, pid)
        return {"ok": True, "grants": rows}

    @mg.post("/grants")
    def api_models_grants_create(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_grant_manager(ctx)
        tid = str(ctx.get("tenant_id") or "").strip()
        pid = str(payload.get("profile_id") or "").strip()
        uid = str(payload.get("user_id") or "").strip()
        if not tid or not pid or not uid:
            raise HTTPException(status_code=400, detail="profile_id_and_user_id_required")
        prof = store.get_llm_profile(pid)
        if not _profile_shareable_for_admin_grant(ctx, prof):
            raise HTTPException(status_code=403, detail="profile_not_shareable")
        actor = str(ctx.get("user_id") or "").strip() or None
        try:
            gid = store.grant_llm_profile_to_user(
                tenant_id=tid,
                profile_id=pid,
                user_id=uid,
                created_by_user_id=actor,
            )
        except ValueError as e:
            code = str(e)
            if code == "profile_not_found":
                raise HTTPException(status_code=404, detail=code) from e
            if code == "user_not_found":
                raise HTTPException(status_code=404, detail=code) from e
            raise HTTPException(status_code=400, detail=code) from e
        return {"ok": True, "grant_id": gid}

    @mg.delete("/grants")
    def api_models_grants_revoke(
        profile_id: str = Query(...),
        user_id: str = Query(...),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_grant_manager(ctx)
        tid = str(ctx.get("tenant_id") or "").strip()
        pid = str(profile_id or "").strip()
        uid = str(user_id or "").strip()
        if not tid or not pid or not uid:
            raise HTTPException(status_code=400, detail="profile_id_and_user_id_required")
        n = store.revoke_llm_profile_grant(tenant_id=tid, profile_id=pid, user_id=uid)
        return {"ok": True, "removed": int(n)}

    @mg.get("/eval")
    def api_models_eval(
        authorization: str | None = Header(default=None),
        limit_logs: int = Query(default=100, ge=1, le=500),
        limit_summary: int = Query(default=500, ge=1, le=5000),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        summary = eval_summary(store, limit=limit_summary)
        logs = store.list_agent_eval_logs(limit=limit_logs)
        return {"ok": True, "summary": summary, "logs": logs}

    _EVAL_EXPORT_FIELDS = (
        "timestamp",
        "session_id",
        "specialist",
        "task_kind",
        "success",
        "latency_ms",
        "cost_hint",
        "notes",
    )

    @mg.get("/eval/export")
    def api_models_eval_export(
        authorization: str | None = Header(default=None),
        format: str = Query(default="csv", description="csv or json"),
        limit: int = Query(default=100_000, ge=1, le=200_000),
    ) -> Response:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        fmt = str(format or "csv").strip().lower()
        rows = store.list_agent_eval_logs(limit=limit)
        if fmt == "json":
            body = json.dumps(rows, ensure_ascii=False, indent=2)
            return Response(
                content=body.encode("utf-8"),
                media_type="application/json; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="agent_eval_logs.json"',
                },
            )
        if fmt != "csv":
            raise HTTPException(status_code=400, detail="invalid_format")
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(_EVAL_EXPORT_FIELDS), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            row = {k: r.get(k) for k in _EVAL_EXPORT_FIELDS}
            if "success" in row:
                row["success"] = 1 if bool(row.get("success")) else 0
            w.writerow(row)
        payload = "\ufeff" + buf.getvalue()
        return Response(
            content=payload.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="agent_eval_logs.csv"'},
        )

    router.include_router(mg)


__all__ = ["include_model_mgmt_routes"]
