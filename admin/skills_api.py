from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException

from oclaw.agents.factory import build_gateway_executor
from oclaw.openclaw_runtime.skill_installer import (
    auto_install_skill_from_payload,
    create_skill_from_template,
    install_skill_from_local_dir,
    install_skill_from_registry_archive,
    list_skills_with_status,
    set_skill_enabled,
)
from oclaw.openclaw_runtime.skill_role_binding import (
    SKILL_ROLE_BINDING_ENABLED_SETTING,
    SKILL_ROLE_BINDING_KEY,
    load_skill_role_binding_dict,
    normalize_skill_role_binding,
    ordered_binding_roles,
    skill_role_binding_enabled,
)
from oclaw.openclaw_runtime.skills_prompt import collect_skill_catalog_entries
from oclaw.openclaw_runtime.skills import _allowed_tool_names_after_wire_policy, discover_workspace_skill_manifests
from oclaw.platform.config.paths import db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.tools.skills.clawhub_client import get_skill_detail as clawhub_get_skill_detail
from oclaw.tools.skills.clawhub_client import search_skills as clawhub_search_skills


def include_skill_routes(
    router: APIRouter,
    *,
    resolve_auth: Callable[[SqliteStore, str | None], dict[str, Any]],
) -> None:
    sk = APIRouter(prefix="/admin/api/skills", tags=["skills"])

    def _require_admin(ctx: dict[str, Any]) -> None:
        perms = set(str(x) for x in (ctx.get("permissions") or []))
        if "admin:read" in perms or str(ctx.get("role") or "") == "owner":
            return
        raise HTTPException(status_code=403, detail="forbidden:admin:read")

    def _require_tenant_write(ctx: dict[str, Any]) -> None:
        perms = set(str(x) for x in (ctx.get("permissions") or []))
        if "admin:tenant:write" in perms or str(ctx.get("role") or "") == "owner":
            return
        raise HTTPException(status_code=403, detail="forbidden:admin:tenant:write")

    def _audit(store: SqliteStore, ctx: dict[str, Any], *, action: str, target_id: str, status: str, detail: dict[str, Any] | None = None) -> None:
        try:
            store.add_admin_audit_log(
                actor_tenant_id=str(ctx.get("tenant_id") or ""),
                actor_user_id=str(ctx.get("user_id") or ""),
                action=action,
                target_type="skill",
                target_id=str(target_id or ""),
                status=status,
                detail=detail or {},
            )
        except Exception:
            pass

    def _normalized_skill_binding(store: SqliteStore) -> tuple[list[str], dict[str, list[str]], set[str]]:
        roles = ordered_binding_roles()
        valid = {str(m.name).strip() for m in discover_workspace_skill_manifests() if str(m.name or "").strip()}
        mapping = normalize_skill_role_binding(
            mapping_raw=load_skill_role_binding_dict(store),
            valid_skill_names=valid,
            available_roles=roles,
        )
        return roles, mapping, valid

    @sk.get("")
    def api_skills_list(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        items = list_skills_with_status(store=store)
        return {"ok": True, "items": items}

    @sk.post("/install")
    def api_skills_install(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        source_dir = str(payload.get("source_dir") or "").strip()
        if not source_dir:
            raise HTTPException(status_code=400, detail="source_dir_required")
        overwrite = bool(payload.get("overwrite"))
        _audit(store, ctx, action="skill_install_started", target_id=source_dir, status="start", detail={"source": "local"})
        out = install_skill_from_local_dir(store=store, source_dir=source_dir, overwrite=overwrite)
        _audit(
            store,
            ctx,
            action="skill_install_finished" if out.ok else "skill_install_failed",
            target_id=out.name or source_dir,
            status="ok" if out.ok else "fail",
            detail={"detail": out.detail, "target_dir": out.target_dir, "source": "local", "input_target": source_dir},
        )
        return {
            "ok": bool(out.ok),
            "result": {
                "name": out.name,
                "target_dir": out.target_dir,
                "detail": out.detail,
                "error_code": out.error_code,
                "retryable": bool(out.retryable),
            },
        }

    @sk.post("/install-registry")
    def api_skills_install_registry(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        archive_url = str(payload.get("archive_url") or "").strip()
        if not archive_url:
            raise HTTPException(status_code=400, detail="archive_url_required")
        overwrite = bool(payload.get("overwrite"))
        _audit(store, ctx, action="skill_install_started", target_id=archive_url, status="start", detail={"source": "registry"})
        out = install_skill_from_registry_archive(store=store, archive_url=archive_url, overwrite=overwrite)
        _audit(
            store,
            ctx,
            action="skill_install_finished" if out.ok else "skill_install_failed",
            target_id=out.name or archive_url,
            status="ok" if out.ok else "fail",
            detail={"detail": out.detail, "target_dir": out.target_dir, "source": "registry", "input_target": archive_url},
        )
        return {
            "ok": bool(out.ok),
            "result": {
                "name": out.name,
                "target_dir": out.target_dir,
                "detail": out.detail,
                "error_code": out.error_code,
                "retryable": bool(out.retryable),
            },
        }

    @sk.get("/market/search")
    def api_skills_market_search(
        q: str | None = None,
        limit: int | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        query = str(q or "").strip()
        lim = int(limit) if isinstance(limit, int) and limit > 0 else 20
        lim = max(1, min(lim, 200))
        items = clawhub_search_skills(query, limit=lim)
        return {"ok": True, "items": items}

    @sk.get("/market/detail")
    def api_skills_market_detail(
        slug: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        s = str(slug or "").strip()
        if not s:
            raise HTTPException(status_code=400, detail="slug_required")
        detail = clawhub_get_skill_detail(s)
        return {"ok": True, "detail": detail}

    @sk.post("/market/install")
    def api_skills_market_install(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        s = str(payload.get("slug") or "").strip()
        if not s:
            raise HTTPException(status_code=400, detail="slug_required")
        requested_version = str(payload.get("version") or "").strip()
        overwrite = bool(payload.get("overwrite"))

        detail = clawhub_get_skill_detail(s)
        archive_url = str(detail.get("archiveUrl") or "").strip()
        chosen_version = str(detail.get("latestVersion") or "").strip()
        if requested_version:
            chosen_version = requested_version
            archive_url = ""
            for v in (detail.get("versions") or []):
                if not isinstance(v, dict):
                    continue
                if str(v.get("version") or "").strip() == requested_version:
                    archive_url = str(v.get("archiveUrl") or "").strip()
                    break

        if not archive_url:
            raise HTTPException(status_code=400, detail="archive_url_unavailable")

        _audit(
            store,
            ctx,
            action="skill_install_started",
            target_id=archive_url,
            status="start",
            detail={"source": "clawhub", "slug": s, "version": chosen_version, "input_target": s},
        )
        out = install_skill_from_registry_archive(store=store, archive_url=archive_url, overwrite=overwrite)
        _audit(
            store,
            ctx,
            action="skill_install_finished" if out.ok else "skill_install_failed",
            target_id=out.name or archive_url,
            status="ok" if out.ok else "fail",
            detail={
                "detail": out.detail,
                "target_dir": out.target_dir,
                "source": "clawhub",
                "slug": s,
                "version": chosen_version,
                "input_target": archive_url,
            },
        )
        return {
            "ok": bool(out.ok),
            "result": {
                "name": out.name,
                "target_dir": out.target_dir,
                "detail": out.detail,
                "error_code": out.error_code,
                "retryable": bool(out.retryable),
            },
        }

    @sk.get("/binding")
    def api_skills_binding_get(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_tenant_write(ctx)
        roles, mapping, _valid = _normalized_skill_binding(store)
        items = list_skills_with_status(store=store)
        return {
            "ok": True,
            "enabled": bool(skill_role_binding_enabled(store=store)),
            "available_roles": roles,
            "installed_skills": items,
            "mapping": mapping,
        }

    @sk.post("/binding")
    def api_skills_binding_save(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_tenant_write(ctx)
        if "enabled" in payload:
            store.set_setting(SKILL_ROLE_BINDING_ENABLED_SETTING, "1" if bool(payload.get("enabled")) else "0")
        roles, _prev_mapping, valid = _normalized_skill_binding(store)
        mapping_raw = payload.get("mapping") if isinstance(payload.get("mapping"), dict) else {}
        mapping = normalize_skill_role_binding(
            mapping_raw=mapping_raw,
            valid_skill_names=valid,
            available_roles=roles,
        )
        store.set_setting(SKILL_ROLE_BINDING_KEY, json.dumps(mapping, ensure_ascii=False))
        _audit(
            store,
            ctx,
            action="skill_binding_update",
            target_id="skill_role_binding",
            status="ok",
            detail={"mapping": mapping, "enabled": bool(skill_role_binding_enabled(store=store))},
        )
        return {
            "ok": True,
            "enabled": bool(skill_role_binding_enabled(store=store)),
            "available_roles": roles,
            "mapping": mapping,
        }

    @sk.get("/effective")
    def api_skills_effective(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        roles, mapping, _valid = _normalized_skill_binding(store)
        role_rows: list[dict[str, Any]] = []
        for role in roles:
            specialist = "generalist" if role == "manager" else role
            ex = build_gateway_executor(store=store, specialist=specialist)
            tools = getattr(ex, "tools", None)
            model = getattr(ex, "model", None)
            if tools is None:
                role_rows.append(
                    {
                        "role": role,
                        "total": 0,
                        "workspace_total": 0,
                        "workspace_direct": 0,
                        "workspace_inherited_manager": 0,
                        "mcp_total": 0,
                        "tool_total": 0,
                        "names_preview": [],
                    }
                )
                continue
            base_url = str(getattr(model, "base_url", "") or "")
            entries = collect_skill_catalog_entries(
                store=store,
                registry=tools,
                base_url=base_url,
                skill_binding_role=role,
            )
            allowed_tool_names, _hidden_tool_names = _allowed_tool_names_after_wire_policy(
                registry=tools,
                store=store,
                base_url=base_url,
            )
            direct_set = set(mapping.get(role) or [])
            manager_set = set(mapping.get("manager") or [])
            workspace_total = 0
            workspace_direct = 0
            workspace_inherited = 0
            workspace_resolved_tool_match = 0
            workspace_docs_only = 0
            mcp_total = 0
            tool_total = 0
            names: list[str] = []
            docs_only_names: list[str] = []
            resolved_workspace_names: list[str] = []
            for nm, _desc, loc in entries:
                names.append(str(nm))
                vloc = str(loc or "")
                if vloc.endswith("SKILL.md"):
                    workspace_total += 1
                    if nm in allowed_tool_names:
                        workspace_resolved_tool_match += 1
                        resolved_workspace_names.append(str(nm))
                    else:
                        workspace_docs_only += 1
                        docs_only_names.append(str(nm))
                    if nm in direct_set:
                        workspace_direct += 1
                    elif role != "manager" and nm in manager_set:
                        workspace_inherited += 1
                elif str(nm).startswith("mcp__"):
                    mcp_total += 1
                else:
                    tool_total += 1
            role_rows.append(
                {
                    "role": role,
                    "total": len(entries),
                    "workspace_total": workspace_total,
                    "workspace_direct": workspace_direct,
                    "workspace_inherited_manager": workspace_inherited,
                    "workspace_resolved_tool_match": workspace_resolved_tool_match,
                    "workspace_docs_only": workspace_docs_only,
                    "mcp_total": mcp_total,
                    "tool_total": tool_total,
                    "names_preview": names[:20],
                    "docs_only_names_preview": docs_only_names[:20],
                    "resolved_workspace_names_preview": resolved_workspace_names[:20],
                }
            )
        return {"ok": True, "enabled": bool(skill_role_binding_enabled(store=store)), "items": role_rows}

    @sk.post("/create")
    def api_skills_create(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        name = str(payload.get("name") or "").strip()
        desc = str(payload.get("description") or "").strip()
        body = str(payload.get("body_markdown") or "").strip()
        md = payload.get("metadata_openclaw")
        md = dict(md) if isinstance(md, dict) else {}
        overwrite = bool(payload.get("overwrite"))
        out = create_skill_from_template(
            store=store,
            name=name,
            description=desc,
            body_markdown=body,
            metadata_openclaw=md,
            overwrite=overwrite,
        )
        _audit(
            store,
            ctx,
            action="skill_create",
            target_id=out.name or name,
            status="ok" if out.ok else "fail",
            detail={"detail": out.detail, "target_dir": out.target_dir},
        )
        return {
            "ok": bool(out.ok),
            "result": {
                "name": out.name,
                "target_dir": out.target_dir,
                "detail": out.detail,
                "error_code": out.error_code,
                "retryable": bool(out.retryable),
            },
        }

    @sk.post("/enable")
    def api_skills_enable(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        name = str(payload.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name_required")
        set_skill_enabled(store=store, skill_name=name, enabled=True)
        _audit(store, ctx, action="skill_enable", target_id=name, status="ok")
        return {"ok": True}

    @sk.post("/disable")
    def api_skills_disable(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        name = str(payload.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name_required")
        set_skill_enabled(store=store, skill_name=name, enabled=False)
        _audit(store, ctx, action="skill_disable", target_id=name, status="ok")
        return {"ok": True}

    @sk.post("/auto-install")
    def api_skills_auto_install(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        auto_name = str(payload.get("name") or "")
        _audit(
            store,
            ctx,
            action="skill_install_started",
            target_id=auto_name,
            status="start",
            detail={"source": "auto", "input_target": auto_name},
        )
        out = auto_install_skill_from_payload(store=store, payload=payload)
        _audit(
            store,
            ctx,
            action="skill_install_finished" if out.ok else "skill_install_failed",
            target_id=out.name or str(payload.get("name") or ""),
            status="ok" if out.ok else "fail",
            detail={"detail": out.detail, "target_dir": out.target_dir, "source": "auto", "input_target": auto_name},
        )
        return {
            "ok": bool(out.ok),
            "result": {
                "name": out.name,
                "target_dir": out.target_dir,
                "detail": out.detail,
                "error_code": out.error_code,
                "retryable": bool(out.retryable),
            },
        }

    @sk.post("/retry-install")
    def api_skills_retry_install(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        source = str(payload.get("source") or "").strip().lower()
        target = str(payload.get("target") or "").strip()
        if source not in {"local", "registry", "auto"}:
            raise HTTPException(status_code=400, detail="invalid_source")
        if not target:
            raise HTTPException(status_code=400, detail="target_required")
        _audit(
            store,
            ctx,
            action="skill_install_started",
            target_id=target,
            status="start",
            detail={"source": source, "retry": True, "input_target": target},
        )
        if source == "local":
            out = install_skill_from_local_dir(store=store, source_dir=target, overwrite=True)
        elif source == "registry":
            out = install_skill_from_registry_archive(store=store, archive_url=target, overwrite=True)
        else:
            out = auto_install_skill_from_payload(
                store=store,
                payload={
                    "name": str(payload.get("name") or "").strip() or target,
                    "description": str(payload.get("description") or "retry auto install"),
                    "body_markdown": str(payload.get("body_markdown") or ""),
                    "metadata_openclaw": dict(payload.get("metadata_openclaw") or {})
                    if isinstance(payload.get("metadata_openclaw"), dict)
                    else {},
                },
            )
        _audit(
            store,
            ctx,
            action="skill_install_finished" if out.ok else "skill_install_failed",
            target_id=out.name or target,
            status="ok" if out.ok else "fail",
            detail={
                "detail": out.detail,
                "target_dir": out.target_dir,
                "source": source,
                "retry": True,
                "input_target": target,
            },
        )
        return {
            "ok": bool(out.ok),
            "result": {
                "name": out.name,
                "target_dir": out.target_dir,
                "detail": out.detail,
                "error_code": out.error_code,
                "retryable": bool(out.retryable),
            },
        }

    @sk.post("/test-run")
    def api_skills_test_run(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = resolve_auth(store, authorization)
        _require_admin(ctx)
        name = str(payload.get("name") or "").strip()
        args = payload.get("args")
        if not name:
            raise HTTPException(status_code=400, detail="name_required")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise HTTPException(status_code=400, detail="args_must_be_object")

        ex = build_gateway_executor(store=store, specialist="generalist")
        tools = getattr(ex, "tools", None)
        if tools is None:
            raise HTTPException(status_code=500, detail="tool_registry_unavailable")
        spec = tools.get(name)
        if spec is None:
            raise HTTPException(status_code=404, detail="tool_not_found")
        try:
            result = spec.handler(dict(args))
        except Exception as exc:
            result = {"ok": False, "error_code": "exception", "error": f"{type(exc).__name__}:{exc}"}

        _audit(
            store,
            ctx,
            action="skill_test_run",
            target_id=name,
            status="ok" if bool((result or {}).get("ok")) else "fail",
            detail={"args_keys": list(args.keys()), "result_ok": bool((result or {}).get("ok"))},
        )
        return {"ok": True, "name": name, "result": result}

    router.include_router(sk)


__all__ = ["include_skill_routes"]

