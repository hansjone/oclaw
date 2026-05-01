from __future__ import annotations

from pathlib import Path
import hashlib
import hmac
import json
import os
import re
import secrets
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, Header, Query
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

from oclaw.runtime.operations.mcp_env import apply_gateway_mcp_env_to_os
from oclaw.runtime.operations.providers.registry import build_channel_registry
from oclaw.runtime.operations.runtime import (
    cleanup_service_processes_by_pid,
    detect_orphan_service_processes,
    is_pid_running,
    list_listen_ports_for_pid,
    list_service_process_pids,
    status_services,
)
from oclaw.runtime.operations.stack import cmd_stack_down, cmd_stack_status, cmd_stack_up
from oclaw.runtime.orchestration.vector_store import read_vector_memory_runtime
from oclaw.platform.config.paths import PROJECT_ROOT, db_path
from oclaw.platform.config.passwords import load_expected_password
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.agents.specialists import discover_specialist_ids
from oclaw.runtime.tools.mcp.installer import (
    _safe_server_id,
    detect_local_dependencies,
    install_mcp_server,
    preflight_mcp_server,
    uninstall_mcp_server,
)
from oclaw.runtime.tools.mcp.market import search_mcp_market, trending_mcp_market
from oclaw.runtime.tools.mcp.manifest import McpServerManifest
from oclaw.runtime.operations.mcp_registry_export import (
    build_mcp_install_export_document,
    mcp_migrated_json_path,
    persist_mcp_migrated_file,
)
from oclaw.runtime.tools.mcp.filesystem_argv import build_mcp_process_command
from oclaw.runtime.tools.mcp.registry import McpRegistry
from oclaw.runtime.tools.mcp.runtime import McpProcessRuntime
from oclaw.interfaces.admin.mcp_e2e_probe import build_mcp_e2e_probe_plans
from oclaw.runtime.tools.catalog import default_registry
from oclaw.runtime.chat.tool_runtime import ToolExecutionContext, ToolExecutor
from oclaw.platform.llm.chat_models import LLMToolCall
from oclaw.runtime.agent_core_attempt import ALL_ATTEMPT_ERROR_CODES
from oclaw.runtime.agent_core_run import DEFAULT_RETRYABLE_ERROR_CODES, resolve_retryable_error_codes
from oclaw.runtime.prompt_prebuild import run_runtime_prewarm, runtime_prewarm_prompts_snapshot, runtime_prewarm_status
from oclaw.runtime.workspaces.experts import (
    create_expert,
    delete_expert,
    list_experts,
    normalize_expert_id,
    update_expert_files,
    update_expert_meta,
)

_WECOM_CLEAR_KEYS = [
    "wecom_mode",
    "wecom_bot_id",
    "wecom_bot_secret",
    "wecom_corp_id",
    "wecom_agent_id",
    "wecom_agent_secret",
    "wecom_access_token_cache",
    "wecom_last_msg_ts",
    "wecom_last_from_user",
    "wecom_recent_from_users",
    "wecom_last_cmd",
    "wecom_last_unknown_cmd_payload",
    "wecom_last_raw_body",
    "wecom_last_raw_from_user",
    "wecom_last_parse_error",
]


def _wecom_bot_secret_key(tenant_id: str, user_id: str, account_id: str) -> str:
    return f"wecom:bot_secret:{tenant_id}:{user_id}:{account_id}"


def _expand_mcp_entry_args(raw: list[Any] | None) -> list[str]:
    """Expand ``__REPO_ROOT__/...`` in argv (same as ``scripts/seed_mcp_registry.py``)."""
    out: list[str] = []
    for x in raw or []:
        s = str(x).strip()
        if not s:
            continue
        if s.startswith("__REPO_ROOT__/"):
            rel = s.replace("__REPO_ROOT__/", "", 1)
            s = str((PROJECT_ROOT / rel).resolve())
        out.append(s)
    return out


def _mcp_health_and_sync_one(store: SqliteStore, row: dict[str, Any]) -> dict[str, Any] | None:
    """Run MCP initialize health + tools/list + persist tools (same semantics as check-all per row)."""
    sid = str(row.get("server_id") or "").strip()
    cmd = str(row.get("entry_command") or "").strip()
    args = [str(x) for x in (row.get("entry_args") or []) if str(x).strip()]
    if not sid:
        return None
    if not cmd:
        item: dict[str, Any] = {
            "server_id": sid,
            "ok": False,
            "error_code": "mcp_entry_missing",
            "error": "entry_command_missing",
            "health": {"ok": False, "error_code": "mcp_entry_missing", "error": "entry_command_missing"},
            "tools_synced": 0,
        }
        store.set_mcp_server_health(server_id=sid, status="error", detail=item["health"])
        return item
    if _is_bailian_webparser_remote(entry_command=cmd, entry_args=args):
        tools = _bailian_webparser_virtual_tools()
        store.replace_mcp_server_tools(server_id=sid, tools=tools)
        detail = {"synced_tools": len(tools), "compat_mode": "bailian_webparser"}
        store.set_mcp_server_health(server_id=sid, status="ok", detail=detail)
        return {"server_id": sid, "ok": True, "health": detail, "tools_synced": len(tools)}
    rt = McpProcessRuntime(
        build_mcp_process_command(cmd, args, store=store),
        timeout_s=float(row.get("timeout_s") or 30.0),
    )
    try:
        health = rt.health()
        health_ok = bool(health.get("ok"))
        if not health_ok:
            item = {
                "server_id": sid,
                "ok": False,
                "error_code": str(health.get("error_code") or "mcp_healthcheck_failed"),
                "error": str(health.get("error") or "healthcheck_failed"),
                "health": health,
                "tools_synced": 0,
            }
            store.set_mcp_server_health(server_id=sid, status="error", detail=health)
            return item
        tools_res = rt.tools_list()
        if not bool(tools_res.get("ok")):
            item = {
                "server_id": sid,
                "ok": False,
                "error_code": str(tools_res.get("error_code") or "mcp_tools_list_invalid"),
                "error": str(tools_res.get("error") or "tools_list_failed"),
                "health": health,
                "tools_synced": 0,
            }
            store.set_mcp_server_health(server_id=sid, status="error", detail=tools_res)
            return item
        tools = tools_res.get("tools") if isinstance(tools_res.get("tools"), list) else []
        store.replace_mcp_server_tools(server_id=sid, tools=tools if isinstance(tools, list) else [])
        store.set_mcp_server_health(server_id=sid, status="ok", detail={"synced_tools": len(tools)})
        return {"server_id": sid, "ok": True, "health": health, "tools_synced": len(tools)}
    finally:
        rt.stop()


def _is_bailian_webparser_remote(*, entry_command: str, entry_args: list[str]) -> bool:
    cmd = str(entry_command or "").strip().lower()
    if cmd not in {"npx", "npx.cmd", "node"}:
        return False
    joined = " ".join(str(x or "").strip().lower() for x in (entry_args or []))
    return "mcp-remote" in joined and "/api/v1/mcps/webparser/sse" in joined


def _bailian_webparser_virtual_tools() -> list[dict[str, Any]]:
    return [
        {
            "tool_name": "bailian_webparser_parse",
            "description": "Parse webpage via DashScope WebParser compatibility mode. Requires `url` (http/https).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target webpage URL (required). Example: https://example.com"},
                    "timeout": {"type": "integer", "default": 35, "minimum": 8, "maximum": 90},
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        }
    ]


def _http_get_json(url: str, *, timeout: float = 8.0) -> dict[str, Any]:
    req = urllib_request.Request(
        url,
        headers={
            "accept": "application/json",
            "user-agent": "oclaw-admin-mcp-check/1.0",
        },
        method="GET",
    )
    with urllib_request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    data = json.loads(raw) if raw else {}
    return data if isinstance(data, dict) else {}


def _github_repo_from_source_ref(source_ref: str) -> str:
    s = str(source_ref or "").strip()
    if not s:
        return ""
    m = re.search(r"github\.com[:/]+([^/]+)/([^/#]+)", s, re.I)
    if m:
        owner = str(m.group(1) or "").strip()
        repo = str(m.group(2) or "").strip().removesuffix(".git")
        return f"{owner}/{repo}" if owner and repo else ""
    if re.fullmatch(r"[^/\s]+/[^/\s]+", s):
        return s
    return ""


def _detect_mcp_latest_version(source_type: str, source_ref: str) -> tuple[str, str]:
    st = str(source_type or "").strip().lower()
    sr = str(source_ref or "").strip()
    if st == "npm":
        pkg = urllib_parse.quote(sr, safe="@/")
        data = _http_get_json(f"https://registry.npmjs.org/{pkg}")
        tags = data.get("dist-tags") if isinstance(data.get("dist-tags"), dict) else {}
        latest = str(tags.get("latest") or "").strip()
        return latest, "npm:dist-tags.latest"
    if st == "pypi":
        pkg = urllib_parse.quote(sr, safe="")
        data = _http_get_json(f"https://pypi.org/pypi/{pkg}/json")
        info = data.get("info") if isinstance(data.get("info"), dict) else {}
        latest = str(info.get("version") or "").strip()
        return latest, "pypi:info.version"
    if st == "github":
        repo = _github_repo_from_source_ref(sr)
        if not repo:
            return "", "github:repo_parse_failed"
        try:
            data = _http_get_json(f"https://api.github.com/repos/{repo}/releases/latest")
            latest = str(data.get("tag_name") or data.get("name") or "").strip()
            if latest:
                return latest, "github:releases.latest"
        except Exception:
            pass
        data2 = _http_get_json(f"https://api.github.com/repos/{repo}/tags?per_page=1")
        if isinstance(data2, list):  # defensive; _http_get_json returns dict for objects
            return "", "github:tags_empty"
        # GitHub tags endpoint returns list; if parse failed to dict, try raw fetch.
        req = urllib_request.Request(
            f"https://api.github.com/repos/{repo}/tags?per_page=1",
            headers={"accept": "application/json", "user-agent": "oclaw-admin-mcp-check/1.0"},
            method="GET",
        )
        with urllib_request.urlopen(req, timeout=8.0) as resp:
            arr_raw = resp.read().decode("utf-8", errors="ignore")
        arr = json.loads(arr_raw) if arr_raw else []
        if isinstance(arr, list) and arr:
            top = arr[0] if isinstance(arr[0], dict) else {}
            return str(top.get("name") or "").strip(), "github:tags[0]"
        return "", "github:no_release_or_tag"
    return "", "unsupported_source_type"


def _check_mcp_update_row(row: dict[str, Any]) -> dict[str, Any]:
    sid = str(row.get("server_id") or "").strip()
    source_type = str(row.get("source_type") or "").strip().lower()
    source_ref = str(row.get("source_ref") or "").strip()
    current_version = str(row.get("version") or "").strip()
    out = {
        "server_id": sid,
        "source_type": source_type,
        "source_ref": source_ref,
        "current_version": current_version,
        "latest_version": "",
        "has_update": False,
        "check_error": "",
        "check_source": "",
    }
    try:
        latest, src = _detect_mcp_latest_version(source_type, source_ref)
        out["latest_version"] = latest
        out["check_source"] = src
        if latest and current_version and current_version not in {"latest", "*"} and current_version != latest:
            out["has_update"] = True
    except Exception as exc:
        out["check_error"] = f"{type(exc).__name__}: {exc}"
    return out


def _enrich_wecom_channel_account(store: SqliteStore, tenant_id: str, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
    aid = str(item.get("account_id") or "")
    cfg = item.get("config")
    if not isinstance(cfg, dict):
        cfg = {}
    out = dict(item)
    out["has_bot_secret"] = bool(store.get_secret(_wecom_bot_secret_key(tenant_id, user_id, aid)))
    out["wecom_mode"] = "bot_api"
    return out


def admin_static_dir() -> Path:
    return Path(__file__).resolve().parent / "static"


def build_admin_router() -> APIRouter:
    router = APIRouter()

    static_dir = admin_static_dir()

    def _sha256_hex(v: str) -> str:
        return hashlib.sha256(str(v or "").encode("utf-8", errors="ignore")).hexdigest()

    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    def _parse_iso(v: str) -> datetime | None:
        try:
            return datetime.fromisoformat(str(v))
        except Exception:
            return None

    def _extract_bearer(authorization: str | None) -> str:
        blob = str(authorization or "").strip()
        if not blob:
            return ""
        parts = blob.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        return ""

    def _resolve_auth(store: SqliteStore, authorization: str | None) -> dict[str, Any]:
        token = _extract_bearer(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="missing_bearer_token")
        session = store.get_auth_session(session_token_hash=_sha256_hex(token))
        if not session:
            raise HTTPException(status_code=401, detail="invalid_session")
        if session.get("revoked_at"):
            raise HTTPException(status_code=401, detail="session_revoked")
        expires_at = _parse_iso(str(session.get("expires_at") or ""))
        if expires_at is None or expires_at <= _now_utc():
            raise HTTPException(status_code=401, detail="session_expired")
        user = store.get_user_by_id(
            tenant_id=str(session.get("tenant_id") or ""),
            user_id=str(session.get("user_id") or ""),
        )
        if not user:
            raise HTTPException(status_code=401, detail="user_not_found")
        if not bool(user.get("is_active")):
            raise HTTPException(status_code=403, detail="user_disabled")
        store.touch_auth_session(session_token_hash=str(session.get("session_token_hash") or ""))
        perms = store.list_user_permissions(
            tenant_id=str(user.get("tenant_id") or ""),
            user_id=str(user.get("id") or ""),
            role=str(user.get("role") or "member"),
        )
        return {
            "tenant_id": user["tenant_id"],
            "user_id": user["id"],
            "username": str(user.get("username") or ""),
            "role": user["role"],
            "permissions": perms,
        }

    def _require_permission(ctx: dict[str, Any], permission: str) -> None:
        perms = set(str(x) for x in (ctx.get("permissions") or []))
        if permission in perms:
            return
        if str(ctx.get("role") or "") == "owner":
            return
        raise HTTPException(status_code=403, detail=f"forbidden:{permission}")

    def _require_tenant_scope(ctx: dict[str, Any], tenant_id: str) -> None:
        if str(ctx.get("tenant_id") or "") == str(tenant_id or ""):
            return
        # 控制台仅 administrator 可登录；该账号允许跨租户读写（与单租户会话 tenant_id 解耦）。
        if str(ctx.get("username") or "").strip().lower() == "administrator":
            return
        raise HTTPException(status_code=403, detail="cross_tenant_forbidden")

    def _ordered_specialists() -> list[str]:
        base = [str(k).strip().lower() for k in discover_specialist_ids() if str(k).strip()]
        preferred = [x for x in ("generalist", "ops", "image") if x in set(base)]
        return preferred + [x for x in base if x not in set(preferred)]

    def _ordered_mcp_roles() -> list[str]:
        specs = _ordered_specialists()
        return ["manager", *[x for x in specs if x != "manager"]]

    def _ordered_roles() -> list[str]:
        """Canonical role list used by Admin preview APIs."""
        specs = _ordered_specialists()
        return ["manager", *[x for x in specs if x != "manager"]]

    _EXPERT_ALLOWED_FILES = {"SOUL.md", "ROLE_SYSTEM.md"}

    def _serialize_expert_row(row: dict[str, Any]) -> dict[str, Any]:
        files = row.get("files") if isinstance(row, dict) else {}
        obj = files if isinstance(files, dict) else {}
        return {
            "id": str(row.get("id") or ""),
            "builtin": bool(row.get("builtin")),
            "has_required_soul": bool(row.get("has_required_soul")),
            "display_name_en": str(row.get("display_name_en") or ""),
            "display_name_zh": str(row.get("display_name_zh") or ""),
            "role": str(row.get("role") or "expert"),
            "path": str(row.get("path") or ""),
            "files": {
                "SOUL.md": str(obj.get("SOUL.md") or ""),
                "ROLE_SYSTEM.md": str(obj.get("ROLE_SYSTEM.md") or ""),
            },
        }

    def _sanitize_expert_files_payload(raw: Any) -> dict[str, str]:
        files_raw = raw if isinstance(raw, dict) else {}
        files = {str(k): str(v or "") for k, v in files_raw.items()}
        bad = [k for k in files.keys() if k not in _EXPERT_ALLOWED_FILES]
        if bad:
            raise ValueError("unsupported_file_name")
        return files

    @router.post("/admin/api/tools/internal/reload")
    def api_internal_tools_reload(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")

        from oclaw.runtime.tools.expert_registry import clear_expert_tool_cache
        from oclaw.runtime.tools.public_registry import clear_public_tool_cache

        clear_public_tool_cache()
        clear_expert_tool_cache()

        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="internal_tools_reload",
            target_type="tool_cache",
            target_id="public+expert",
            status="ok",
            detail={"cleared": True},
        )
        return {"ok": True, "cleared": True}

    @router.get("/admin/api/tools/exposure-trace-setting")
    def api_tools_exposure_trace_setting_get(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        raw = str(store.get_setting("AIA_TRACE_TOOL_EXPOSURE_PLAN") or "").strip().lower()
        enabled = raw in {"1", "true", "yes", "on"}
        return {"ok": True, "enabled": bool(enabled)}

    @router.post("/admin/api/tools/exposure-trace-setting")
    def api_tools_exposure_trace_setting_save(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        payload = payload or {}
        enabled = bool(payload.get("enabled"))
        store.set_setting("AIA_TRACE_TOOL_EXPOSURE_PLAN", "1" if enabled else "0")
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="tools_exposure_trace_setting_update",
            target_type="app_setting",
            target_id="AIA_TRACE_TOOL_EXPOSURE_PLAN",
            status="ok",
            detail={"enabled": bool(enabled)},
        )
        return {"ok": True, "enabled": bool(enabled)}

    @router.get("/admin/api/tools/internal/preview")
    def api_internal_tools_preview(
        role: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        from oclaw.runtime.tools.exposure_plan import build_internal_tool_specs

        r = str(role or "").strip().lower()
        available_roles = _ordered_roles()
        if not r:
            r = "generalist" if "generalist" in set(available_roles) else (available_roles[0] if available_roles else "")
        if r not in set(available_roles):
            raise HTTPException(status_code=400, detail="invalid_role")

        specs, diag = build_internal_tool_specs(role=r, preview=True)

        def _to_row(spec: Any, source: str) -> dict[str, Any]:
            return {
                "name": str(getattr(spec, "name", "") or ""),
                "description": str(getattr(spec, "description", "") or ""),
                "tags": sorted([str(x) for x in (getattr(spec, "tags", None) or [])]),
                "read_only": bool(getattr(spec, "read_only", False)),
                "risk_level": str(getattr(spec, "risk_level", "") or ""),
                "timeout_s": float(getattr(spec, "timeout_s", 0.0) or 0.0),
            }

        tools = []
        source_by_name = dict(diag.get("source_by_name") or {})
        for s in specs:
            src = str(source_by_name.get(str(getattr(s, "name", "") or ""), "expert"))
            tools.append({**_to_row(s, src), "source": src})
        tools.sort(key=lambda x: (str(x.get("source") or ""), str(x.get("name") or "")))

        return {"ok": True, "role": r, "available_roles": available_roles, "tools": tools, **diag}

    @router.get("/admin/api/tools/self-check")
    def api_tools_self_check(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """One-shot diagnostic summary for role-based tool exposure."""
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")

        from oclaw.platform.llm.tool_wire_policy import load_role_mode_for_role, load_tool_policies_dict_for_role
        from oclaw.runtime.tools.exposure_plan import build_internal_tool_specs, build_llm_tools_plan

        roles = _ordered_roles()
        items: list[dict[str, Any]] = []
        total_perm_ban = 0
        total_wired = 0
        total_internal = 0
        for role in roles:
            internal_specs, internal_diag = build_internal_tool_specs(role=role, preview=True)
            llm_plan = build_llm_tools_plan(
                store=store,
                role=role,
                base_url=None,
                max_json_bytes=None,
                include_mcp=True,
                preview_internal=True,
            )
            policies = load_tool_policies_dict_for_role(store, role=role)
            perm_ban = len([k for k, v in policies.items() if str(k).startswith("mcp__") and int(v) == 9999])
            total_perm_ban += perm_ban
            total_wired += len(llm_plan.tools_wired)
            total_internal += len(internal_specs)
            items.append(
                {
                    "role": role,
                    "role_mode": load_role_mode_for_role(store, role=role),
                    "internal_count": len(internal_specs),
                    "internal_public_count": int(internal_diag.get("public_count") or 0),
                    "internal_expert_count": int(internal_diag.get("expert_count") or 0),
                    "wired_count": len(llm_plan.tools_wired),
                    "raw_count": len(llm_plan.tools_raw),
                    "removed_total": len(llm_plan.removed_names),
                    "removed_mcp_total": len(llm_plan.removed_mcp_names),
                    "changed_total": len(llm_plan.changed_names),
                    "policy_perm_ban_9999": perm_ban,
                    "mcp_enabled": bool(llm_plan.mcp_enabled),
                    "wire_policy_effective": bool(llm_plan.wire_policy_effective),
                }
            )

        return {
            "ok": True,
            "roles_total": len(roles),
            "roles": roles,
            "summary": {
                "total_internal_tools": total_internal,
                "total_wired_tools": total_wired,
                "total_perm_ban_9999": total_perm_ban,
            },
            "items": items,
        }

    @router.get("/admin/api/tools/llm/preview")
    def api_llm_tools_preview(
        role: str | None = Query(default=None),
        base_url: str | None = Query(default=None),
        max_json_bytes: int | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """Preview the final tools injected to LLM for a role (internal + MCP + wire policy)."""
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        from oclaw.runtime.tools.exposure_plan import build_llm_tools_plan

        r = str(role or "").strip().lower()
        available_roles = _ordered_roles()
        if not r:
            r = "generalist" if "generalist" in set(available_roles) else (available_roles[0] if available_roles else "")
        if r not in set(available_roles):
            raise HTTPException(status_code=400, detail="invalid_role")
        plan = build_llm_tools_plan(
            store=store,
            role=r,
            base_url=base_url,
            max_json_bytes=max_json_bytes,
            include_mcp=True,
            preview_internal=True,
        )
        return {
            "ok": True,
            "role": plan.role,
            "available_roles": available_roles,
            "base_url": plan.base_url,
            "max_json_bytes": plan.max_json_bytes,
            "mcp_enabled": plan.mcp_enabled,
            "role_mode": plan.role_mode,
            "wire_policy_effective": plan.wire_policy_effective,
            "policy_keys": plan.policy_keys,
            "raw_count": len(plan.tools_raw),
            "wired_count": len(plan.tools_wired),
            "removed_mcp_names": plan.removed_mcp_names,
            "tools_raw": plan.tools_raw,
            "tools_wired": plan.tools_wired,
            "public_risk_gate_allow_high": plan.public_risk_gate_allow_high,
            "public_blocked_high_risk_tools": plan.public_blocked_high_risk_tools,
            "skipped_public": plan.skipped_public,
            "skipped_expert": plan.skipped_expert,
        }

    def _load_mcp_specialist_binding(store: SqliteStore) -> dict[str, list[str]]:
        raw = str(store.get_setting("mcp_specialist_server_binding") or "").strip()
        if not raw:
            return {}
        try:
            obj = json.loads(raw)
        except Exception:
            return {}
        if not isinstance(obj, dict):
            return {}
        out: dict[str, list[str]] = {}
        for k, v in obj.items():
            sid = str(k or "").strip().lower()
            if not sid:
                continue
            items = v if isinstance(v, list) else []
            vals = [str(x).strip() for x in items if str(x).strip()]
            out[sid] = vals
        return out

    def _normalize_mcp_specialist_binding(
        *,
        available_specialists: list[str],
        servers: list[dict[str, Any]],
        mapping: dict[str, Any],
    ) -> dict[str, list[str]]:
        available_set = set(available_specialists)
        server_ids = {str(x.get("server_id") or "").strip() for x in servers if str(x.get("server_id") or "").strip()}
        out: dict[str, list[str]] = {}
        for sp in available_specialists:
            rows = mapping.get(sp) if isinstance(mapping, dict) else None
            items = rows if isinstance(rows, list) else []
            vals = []
            seen: set[str] = set()
            for x in items:
                sid = str(x or "").strip()
                if not sid or sid not in server_ids or sid in seen:
                    continue
                seen.add(sid)
                vals.append(sid)
            out[sp] = vals
        # drop any unknown specialist keys by only returning available list keys
        for key in list(out.keys()):
            if key not in available_set:
                out.pop(key, None)
        return out

    def _ensure_admin_bootstrap(store: SqliteStore) -> None:
        tenants = store.list_tenants(limit=500)
        if not tenants:
            store.create_tenant("Team")
            tenants = store.list_tenants(limit=500)
        pwd = load_expected_password(store)
        if not pwd:
            # Fail closed: require explicit password configuration.
            raise HTTPException(
                status_code=400,
                detail="missing_admin_password: set AIA_ASSISTANT_PASSWORD env or store secret auth_password first",
            )
        pwd_hash = _sha256_hex(pwd)
        for tenant in tenants:
            tid = str((tenant or {}).get("id") or "").strip()
            if not tid:
                continue
            if store.get_user_by_username(tenant_id=tid, username="administrator"):
                continue
            store.create_user_account(
                tenant_id=tid,
                username="administrator",
                display_name="Administrator",
                role="admin",
                password_hash=pwd_hash,
                is_active=True,
            )

    @router.get("/admin", response_class=HTMLResponse)
    def admin_root() -> Any:
        p = static_dir / "index.html"
        return HTMLResponse(p.read_text(encoding="utf-8"))

    @router.get("/admin/api/channels")
    def api_channels(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = _resolve_auth(SqliteStore(db_path()), authorization)
        _require_permission(ctx, "admin:read")
        reg = build_channel_registry()
        items = [{"name": k, "type": reg[k].__class__.__name__} for k in sorted(reg.keys())]
        return {"ok": True, "channels": items}

    @router.get("/admin/api/stack/status")
    def api_stack_status(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = _resolve_auth(SqliteStore(db_path()), authorization)
        _require_permission(ctx, "admin:read")
        items = []
        for s in status_services():
            all_pids = list_service_process_pids(str(s.name))
            pid_ports: dict[str, list[int]] = {}
            pid_running: dict[str, bool] = {}
            ports_set: set[int] = set()
            for p in all_pids:
                pp = list_listen_ports_for_pid(int(p))
                pid_ports[str(int(p))] = [int(x) for x in pp]
                pid_running[str(int(p))] = bool(is_pid_running(int(p)))
                for x in pp:
                    ports_set.add(int(x))
            running_any = any(bool(v) for v in pid_running.values()) if pid_running else bool(s.running)
            # Choose primary pid from the current snapshot (do not "stick" to state pid).
            live = sorted([int(k) for k, v in pid_running.items() if v])
            primary_pid = 0
            if live:
                name = str(getattr(s, "name", "") or "")
                # Prefer gateway PID that actually binds the gateway port.
                if name == "gateway":
                    prefer_port = 8787
                    candidates = [p for p in live if int(prefer_port) in set(pid_ports.get(str(p), []) or [])]
                    if candidates:
                        primary_pid = int(candidates[0])
                if not primary_pid:
                    # Prefer PID(s) with any listening ports.
                    with_ports = [p for p in live if (pid_ports.get(str(p), []) or [])]
                    if with_ports:
                        # Choose the one with most ports, tie-breaker: smallest pid
                        with_ports.sort(key=lambda p: (-len(pid_ports.get(str(p), []) or []), int(p)))
                        primary_pid = int(with_ports[0])
                if not primary_pid:
                    # Fall back to smallest live pid for stability.
                    primary_pid = int(live[0])
            items.append(
                {
                    "name": s.name,
                    "pid": int(primary_pid or 0),
                    "running": bool(running_any),
                    "all_pids": sorted(int(x) for x in all_pids if int(x) > 0),
                    "ports": sorted(ports_set),
                    "pid_ports": pid_ports,
                    "pid_running": pid_running,
                    "duplicate_count": max(0, len(set(int(x) for x in all_pids if int(x) > 0)) - 1),
                }
            )
        return {"ok": True, "items": items}

    @router.post("/admin/api/stack/up")
    def api_stack_up(channel: str = "wecom", authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = _resolve_auth(SqliteStore(db_path()), authorization)
        _require_permission(ctx, "admin:runtime:write")
        # Use same defaults as CLI; this starts detached processes and writes runtime state.
        import argparse

        ns = argparse.Namespace(
            channel=channel,
            channel_mode="ws",
            channel_interval=3.0,
            deliver_outbound=True,
            pull_url=None,
            gateway_host="0.0.0.0",
            gateway_port=8787,
            with_ui=False,
            ui_port=8501,
        )
        cmd_stack_up(ns)
        return api_stack_status()

    @router.post("/admin/api/stack/down")
    def api_stack_down(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = _resolve_auth(SqliteStore(db_path()), authorization)
        _require_permission(ctx, "admin:runtime:write")
        import argparse

        ns = argparse.Namespace()
        cmd_stack_down(ns)
        return api_stack_status()

    def _collect_runtime_anomalies(store: SqliteStore) -> dict[str, Any]:
        items = []
        running = status_services()
        for s in running:
            if not bool(getattr(s, "running", False)):
                # Duplicate worker checks only make sense when a primary service
                # is currently running. Otherwise this creates noisy conflicts
                # with "missing service" alerts.
                continue
            keep = {int(s.pid)} if s.running and int(s.pid or 0) > 0 else set()
            all_pids = list_service_process_pids(s.name)
            if (not keep) and len(all_pids) > 1:
                # Ambiguous primary process: do not guess and do not auto-clean.
                # Require explicit stack restart to re-elect primary PID safely.
                items.append(
                    {
                        "type": "duplicate_process_ambiguous",
                        "service": s.name,
                        "expected_pid": 0,
                        "orphan_pids": sorted(int(x) for x in all_pids),
                        "severity": "critical",
                        "message": (
                            f"{s.name} has multiple workers but no stable primary pid in runtime state: "
                            f"{', '.join(str(x) for x in sorted(all_pids))}. "
                            "Please restart stack (down/up)."
                        ),
                    }
                )
                continue
            orphans = detect_orphan_service_processes(s.name, keep_pids=keep)
            if orphans:
                items.append(
                    {
                        "type": "duplicate_process",
                        "service": s.name,
                        "expected_pid": int(s.pid or 0),
                        "orphan_pids": sorted(int(x) for x in orphans),
                        "severity": "critical",
                        "message": f"{s.name} has duplicate workers: {', '.join(str(x) for x in sorted(orphans))}",
                    }
                )
        last_parse_error = str(store.get_setting("wecom_last_parse_error") or "").strip()
        last_outbound_error = str(store.get_setting("wecom_last_outbound_error") or "").strip()
        if last_parse_error:
            sev = "warning"
            if "disconnected_event" in last_parse_error.lower():
                sev = "critical"
            items.append(
                {
                    "type": "wecom_parse_error",
                    "service": "channel:wecom",
                    "severity": sev,
                    "message": f"wecom_last_parse_error={last_parse_error}",
                }
            )
        if last_outbound_error:
            items.append(
                {
                    "type": "wecom_outbound_error",
                    "service": "channel:wecom",
                    "severity": "critical",
                    "message": f"wecom_last_outbound_error={last_outbound_error}",
                }
            )
        must_cleanup = any(str(x.get("type") or "") == "duplicate_process" for x in items)
        return {"ok": True, "must_cleanup": must_cleanup, "items": items}

    @router.get("/admin/api/runtime/anomalies")
    def api_runtime_anomalies(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        return _collect_runtime_anomalies(store)

    @router.post("/admin/api/runtime/cleanup")
    def api_runtime_cleanup(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:runtime:write")
        killed: list[dict[str, Any]] = []
        # Cleanup rule:
        # - show all PIDs to user; cleanup should be conservative.
        # - for a service with multiple workers, kill those with NO listening ports.
        # - never delete the last remaining worker for a service.
        for s in status_services():
            service = str(getattr(s, "name", "") or "").strip()
            if not service:
                continue
            all_pids = [int(x) for x in list_service_process_pids(service) if int(x) > 0]
            if len(all_pids) <= 1:
                continue
            pid_ports: dict[int, list[int]] = {int(p): list_listen_ports_for_pid(int(p)) for p in all_pids}
            with_ports = [p for p in all_pids if pid_ports.get(int(p))]
            without_ports = [p for p in all_pids if not pid_ports.get(int(p))]
            victims: list[int] = []
            if with_ports:
                victims = list(without_ports)
            else:
                # If none are listening (e.g. long-polling channel workers),
                # keep the recorded primary pid when possible, otherwise keep the first.
                primary = int(getattr(s, "pid", 0) or 0)
                keep = primary if primary in all_pids else int(all_pids[0])
                victims = [p for p in all_pids if int(p) != int(keep)]
            if victims and len(victims) >= len(all_pids):
                victims = victims[: max(0, len(all_pids) - 1)]
            dead = cleanup_service_processes_by_pid(service, victims)
            if dead:
                killed.append({"service": service, "killed_pids": sorted(int(x) for x in dead)})
        anomalies = _collect_runtime_anomalies(store)
        return {"ok": True, "killed": killed, "anomalies": anomalies}

    @router.get("/admin/api/runtime/prewarm/status")
    def api_runtime_prewarm_status(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        return runtime_prewarm_status(store=store)

    @router.post("/admin/api/runtime/prewarm")
    def api_runtime_prewarm(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:runtime:write")
        body = payload or {}
        mode = str(body.get("mode") or "async").strip().lower()
        reason = str(body.get("reason") or "admin_manual").strip() or "admin_manual"
        if mode == "sync":
            return run_runtime_prewarm(reason=reason, store=store)
        import threading

        def _run() -> None:
            try:
                _ = run_runtime_prewarm(reason=reason, store=SqliteStore(db_path()))
            except Exception:
                pass

        th = threading.Thread(target=_run, name="oclaw-admin-prewarm", daemon=True)
        th.start()
        return {"ok": True, "accepted": True, "mode": "async", "status": runtime_prewarm_status(store=store)}

    @router.get("/admin/api/runtime/prewarm/prompts")
    def api_runtime_prewarm_prompts(
        role: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        return runtime_prewarm_prompts_snapshot(store=store, role=str(role or "").strip().lower() or None)

    @router.get("/admin/api/runtime/scan-artifacts")
    def api_runtime_scan_artifacts(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = _resolve_auth(SqliteStore(db_path()), authorization)
        _require_permission(ctx, "admin:read")
        root = (PROJECT_ROOT / "runtime" / "data" / "scan").resolve()
        allowed_prefixes = ("history_entries_", "state_scan_")
        items: list[dict[str, Any]] = []
        if root.exists() and root.is_dir():
            for p in sorted(root.glob("*.json"), key=lambda x: x.name.lower()):
                if not p.name.startswith(allowed_prefixes):
                    continue
                try:
                    st = p.stat()
                    items.append(
                        {
                            "name": p.name,
                            "path": str(p),
                            "bytes": int(st.st_size),
                            "modified_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                        }
                    )
                except Exception:
                    continue
        return {"ok": True, "dir": str(root), "count": len(items), "items": items}

    @router.post("/admin/api/runtime/scan-artifacts/cleanup")
    def api_runtime_scan_artifacts_cleanup(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = _resolve_auth(SqliteStore(db_path()), authorization)
        _require_permission(ctx, "admin:runtime:write")
        root = (PROJECT_ROOT / "runtime" / "data" / "scan").resolve()
        allowed_prefixes = ("history_entries_", "state_scan_")
        removed = 0
        if root.exists() and root.is_dir():
            for p in root.glob("*.json"):
                if not p.name.startswith(allowed_prefixes):
                    continue
                try:
                    p.unlink(missing_ok=True)
                    removed += 1
                except Exception:
                    continue
        return {"ok": True, "dir": str(root), "removed": int(removed)}

    @router.post("/admin/api/runtime/scan-artifacts/prune")
    def api_runtime_scan_artifacts_prune(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        body = payload or {}
        ctx = _resolve_auth(SqliteStore(db_path()), authorization)
        _require_permission(ctx, "admin:runtime:write")
        root = (PROJECT_ROOT / "runtime" / "data" / "scan").resolve()
        try:
            keep_latest = int(body.get("keep_latest", 20))
        except Exception:
            keep_latest = 20
        try:
            max_age_days = int(body.get("max_age_days", 7))
        except Exception:
            max_age_days = 7
        keep_latest = max(0, min(keep_latest, 500))
        max_age_days = max(0, min(max_age_days, 3650))
        allowed_prefixes = ("history_entries_", "state_scan_")
        rows: list[tuple[Path, float]] = []
        if root.exists() and root.is_dir():
            for p in root.glob("*.json"):
                if not p.name.startswith(allowed_prefixes):
                    continue
                try:
                    rows.append((p, float(p.stat().st_mtime)))
                except Exception:
                    continue
        rows.sort(key=lambda x: x[1], reverse=True)
        cutoff_ts = None
        if max_age_days > 0:
            cutoff_ts = (_now_utc() - timedelta(days=max_age_days)).timestamp()
        removed = 0
        for idx, (p, mtime) in enumerate(rows):
            remove_by_rank = keep_latest >= 0 and idx >= keep_latest
            remove_by_age = cutoff_ts is not None and mtime < cutoff_ts
            if not remove_by_rank and not remove_by_age:
                continue
            try:
                p.unlink(missing_ok=True)
                removed += 1
            except Exception:
                continue
        return {
            "ok": True,
            "dir": str(root),
            "removed": int(removed),
            "keep_latest": int(keep_latest),
            "max_age_days": int(max_age_days),
        }

    @router.get("/admin/api/tenants")
    def api_tenants(
        scope: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:read")
        rows = store.list_tenants(limit=500)
        if str(scope or "").strip().lower() == "mine":
            tid = str(ctx.get("tenant_id") or "").strip()
            rows = [r for r in rows if str(r.get("id") or "") == tid]
        return {"ok": True, "tenants": rows}

    @router.post("/admin/api/tenants/create")
    def api_tenants_create(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        name = str(payload.get("name") or "").strip() or "Team"
        tenant = store.create_tenant(name)
        return {"ok": True, "tenant": tenant}

    @router.post("/admin/api/tenants/delete")
    def api_tenants_delete(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        tenant_id = str(payload.get("tenant_id") or "").strip()
        _require_tenant_scope(ctx, tenant_id)
        if not tenant_id:
            return {"ok": False, "error": "tenant_id is required"}
        all_tenants = store.list_tenants(limit=1000)
        if len(all_tenants) <= 1:
            return {"ok": False, "error": "last_tenant_cannot_delete"}
        if tenant_id == str(ctx.get("tenant_id") or "").strip():
            return {"ok": False, "error": "cannot_delete_current_tenant"}
        if not any(str(r.get("id") or "") == tenant_id for r in all_tenants):
            return {"ok": False, "error": "tenant_not_found"}
        deleted = store.delete_tenant(tenant_id=tenant_id)
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="tenant_delete",
            target_type="tenant",
            target_id=tenant_id,
            status="ok" if deleted > 0 else "miss",
        )
        return {"ok": True, "deleted": deleted}

    @router.get("/admin/api/bindings")
    def api_bindings(
        tenant_id: str,
        channel: str = "wecom",
        user_id: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:read")
        _require_tenant_scope(ctx, tenant_id)
        uid = str(user_id or "").strip() or None
        # Prefer v2 bindings for WeCom (includes account_id + account_name).
        if str(channel or "").strip().lower() == "wecom":
            rows = store.list_channel_identities_v2(
                tenant_id=tenant_id, channel=channel, user_id=uid, limit=2000
            )
        else:
            rows = store.list_channel_identities(tenant_id=tenant_id, channel=channel, limit=1000)
            if uid:
                rows = [r for r in rows if str(r.get("user_id") or "") == uid]
        return {"ok": True, "bindings": rows, "version": 2 if str(channel or "").strip().lower() == "wecom" else 1}

    @router.get("/admin/api/user-channel-accounts")
    def api_user_channel_accounts(
        tenant_id: str,
        user_id: str,
        channel: str = "wecom",
        include_inactive: int = Query(default=1),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:read")
        _require_tenant_scope(ctx, tenant_id)
        rows = store.list_user_channel_accounts(
            tenant_id=tenant_id,
            user_id=user_id,
            channel=channel,
            include_inactive=bool(int(include_inactive or 0)),
        )
        if str(channel or "").strip().lower() == "wecom":
            rows = [_enrich_wecom_channel_account(store, tenant_id, user_id, dict(x)) for x in rows]
        return {"ok": True, "items": rows}

    @router.post("/admin/api/user-channel-accounts/upsert")
    def api_user_channel_accounts_upsert(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:write")
        tenant_id = str(payload.get("tenant_id") or "").strip()
        user_id = str(payload.get("user_id") or "").strip()
        channel = str(payload.get("channel") or "wecom").strip() or "wecom"
        account_id = str(payload.get("account_id") or "").strip()
        name = str(payload.get("name") or "").strip()
        _require_tenant_scope(ctx, tenant_id)
        if not tenant_id or not user_id or not account_id:
            return {"ok": False, "error": "tenant_id, user_id, account_id are required"}
        if not store.get_user_by_id(tenant_id=tenant_id, user_id=user_id):
            return {"ok": False, "error": "user_not_found"}
        is_active = payload.get("is_active")
        cfg: dict[str, Any] = {}
        existing_rows = store.list_user_channel_accounts(
            tenant_id=tenant_id, user_id=user_id, channel=channel, include_inactive=True
        )
        cur_row = next((x for x in existing_rows if str(x.get("account_id") or "") == account_id), None)
        if cur_row and isinstance(cur_row.get("config"), dict):
            cfg = dict(cur_row["config"])
        if isinstance(payload.get("config"), dict):
            cfg.update(payload["config"])
        if str(channel or "").strip().lower() == "wecom":
            cfg["wecom_mode"] = "bot_api"
            cfg.pop("wecom_corp_id", None)
            cfg.pop("wecom_agent_id", None)
            bot_secret = str(payload.get("wecom_bot_secret") or payload.get("bot_secret") or "").strip()
            if bot_secret:
                store.set_secret(_wecom_bot_secret_key(tenant_id, user_id, account_id), bot_secret)
            if payload.get("clear_bot_secret") is True:
                store.delete_setting(_wecom_bot_secret_key(tenant_id, user_id, account_id))
        store.upsert_user_channel_account(
            tenant_id=tenant_id,
            user_id=user_id,
            channel=channel,
            account_id=account_id,
            name=name,
            config=cfg,
            is_active=bool(is_active) if isinstance(is_active, bool) else True,
        )
        rows = store.list_user_channel_accounts(tenant_id=tenant_id, user_id=user_id, channel=channel, include_inactive=True)
        row = next((x for x in rows if str(x.get("account_id") or "") == account_id), None)
        if str(channel or "").strip().lower() == "wecom" and row:
            row = _enrich_wecom_channel_account(store, tenant_id, user_id, dict(row))
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="user_channel_account_upsert",
            target_type="user_channel_account",
            target_id=f"{tenant_id}:{user_id}:{channel}:{account_id}",
            status="ok",
            detail={"name": name, "is_active": bool((row or {}).get("is_active", True))},
        )
        return {"ok": True, "item": row or {}}

    @router.post("/admin/api/user-channel-accounts/delete")
    def api_user_channel_accounts_delete(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:write")
        tenant_id = str(payload.get("tenant_id") or "").strip()
        user_id = str(payload.get("user_id") or "").strip()
        channel = str(payload.get("channel") or "wecom").strip() or "wecom"
        account_id = str(payload.get("account_id") or "").strip()
        _require_tenant_scope(ctx, tenant_id)
        if not tenant_id or not user_id or not account_id:
            return {"ok": False, "error": "tenant_id, user_id, account_id are required"}
        deleted = store.delete_user_channel_account(
            tenant_id=tenant_id,
            user_id=user_id,
            channel=channel,
            account_id=account_id,
        )
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="user_channel_account_delete",
            target_type="user_channel_account",
            target_id=f"{tenant_id}:{user_id}:{channel}:{account_id}",
            status="ok" if deleted > 0 else "miss",
        )
        return {"ok": True, "deleted": deleted}

    @router.get("/admin/api/users")
    def api_users(
        tenant_id: str,
        q: str | None = Query(default=None),
        include_inactive: int = Query(default=1),
        offset: int = Query(default=0),
        limit: int = Query(default=1000),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:read")
        _require_tenant_scope(ctx, tenant_id)
        rows = store.list_users(
            tenant_id=tenant_id,
            q=q,
            include_inactive=bool(int(include_inactive or 0)),
            offset=offset,
            limit=limit,
        )
        return {"ok": True, "users": rows}

    @router.post("/admin/api/users/create")
    def api_users_create(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:write")
        tenant_id = str(payload.get("tenant_id") or "").strip() or str(ctx.get("tenant_id") or "").strip()
        _require_tenant_scope(ctx, tenant_id)
        username = str(payload.get("username") or "").strip().lower()
        display_name = str(payload.get("display_name") or username or "User").strip()
        role = str(payload.get("role") or "member").strip() or "member"
        password = str(payload.get("password") or "").strip()
        if not username or not password:
            return {"ok": False, "error": "username, password are required"}
        existing = store.get_user_by_username(tenant_id=tenant_id, username=username)
        if existing:
            return {"ok": False, "error": "username_conflict"}
        row = store.create_user_account(
            tenant_id=tenant_id,
            username=username,
            display_name=display_name,
            role=role,
            password_hash=_sha256_hex(password),
            is_active=True,
        )
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="user_create",
            target_type="user",
            target_id=str(row.get("id") or ""),
            status="ok",
            detail={"username": username, "role": role},
        )
        return {"ok": True, "user": row}

    @router.post("/admin/api/users/update")
    def api_users_update(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:write")
        tenant_id = str(payload.get("tenant_id") or "").strip()
        user_id = str(payload.get("user_id") or "").strip()
        _require_tenant_scope(ctx, tenant_id)
        if not tenant_id or not user_id:
            return {"ok": False, "error": "tenant_id and user_id are required"}
        target = store.get_user_by_id(tenant_id=tenant_id, user_id=user_id)
        if not target:
            return {"ok": False, "error": "user_not_found"}
        if str(target.get("username") or "").strip().lower() == "administrator" and payload.get("is_active") is False:
            return {"ok": False, "error": "administrator_cannot_be_disabled"}
        pwd = payload.get("password")
        ok = store.update_user_account(
            tenant_id=tenant_id,
            user_id=user_id,
            display_name=payload.get("display_name"),
            role=payload.get("role"),
            is_active=payload.get("is_active") if isinstance(payload.get("is_active"), bool) else None,
            password_hash=_sha256_hex(str(pwd)) if isinstance(pwd, str) and pwd.strip() else None,
        )
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="user_update",
            target_type="user",
            target_id=user_id,
            status="ok" if ok else "miss",
            detail={"fields": list(payload.keys())},
        )
        return {"ok": True, "updated": bool(ok)}

    @router.post("/admin/api/users/delete")
    def api_users_delete(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:delete")
        tenant_id = str(payload.get("tenant_id") or "").strip()
        user_id = str(payload.get("user_id") or "").strip()
        _require_tenant_scope(ctx, tenant_id)
        if not tenant_id or not user_id:
            return {"ok": False, "error": "tenant_id and user_id are required"}
        target = store.get_user_by_id(tenant_id=tenant_id, user_id=user_id)
        if not target:
            return {"ok": False, "error": "user_not_found"}
        if str(target.get("username") or "").strip().lower() == "administrator":
            return {"ok": False, "error": "administrator_cannot_be_deleted"}
        if user_id == str(ctx.get("user_id") or ""):
            return {"ok": False, "error": "cannot_delete_self"}
        deleted = store.delete_user_account(tenant_id=tenant_id, user_id=user_id)
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="user_delete",
            target_type="user",
            target_id=user_id,
            status="ok" if deleted > 0 else "miss",
        )
        return {"ok": True, "deleted": deleted}

    def _workspace_path_policy_read_mode(ctx: dict[str, Any]) -> str | None:
        """``full`` = any user in tenant; ``self`` = only own user_id; ``None`` = forbidden."""
        if str(ctx.get("role") or "") == "owner":
            return "full"
        perms = set(str(x) for x in (ctx.get("permissions") or []))
        if "admin:user:read" in perms:
            return "full"
        if "admin:workspace_paths:read" in perms:
            return "self"
        return None

    def _workspace_path_policy_write_mode(ctx: dict[str, Any]) -> str | None:
        if str(ctx.get("role") or "") == "owner":
            return "full"
        perms = set(str(x) for x in (ctx.get("permissions") or []))
        if "admin:user:write" in perms:
            return "full"
        if "admin:workspace_paths:write" in perms:
            return "self"
        return None

    def _normalize_workspace_extra_roots(raw: str) -> tuple[str, str | None]:
        """Split ``|``, resolve each segment; must be absolute. Returns (joined, error_code)."""
        parts = [x.strip().strip('"').strip("'") for x in str(raw or "").split("|") if str(x).strip()]
        if not parts:
            return "", None
        out: list[str] = []
        for p in parts:
            try:
                rp = Path(p).expanduser().resolve()
                if not rp.is_absolute():
                    return "", "extra_roots_must_be_absolute"
                out.append(str(rp))
            except Exception:
                return "", "extra_roots_invalid_path"
        return "|".join(out), None

    @router.get("/admin/api/users/workspace-path-policy")
    def api_users_workspace_path_policy_get(
        tenant_id: str = Query(default=""),
        user_id: str = Query(default=""),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        rmode = _workspace_path_policy_read_mode(ctx)
        if rmode is None:
            raise HTTPException(status_code=403, detail="forbidden")
        tid = str(tenant_id or "").strip()
        uid = str(user_id or "").strip()
        _require_tenant_scope(ctx, tid)
        if not tid or not uid:
            return {"ok": False, "error": "tenant_id and user_id are required"}
        if rmode == "self" and (tid != str(ctx.get("tenant_id") or "") or uid != str(ctx.get("user_id") or "")):
            raise HTTPException(status_code=403, detail="workspace_paths_self_only")
        row = store.get_user_workspace_path_allowlist(tenant_id=tid, user_id=uid)
        if not row:
            return {
                "ok": True,
                "from_db": False,
                "policy": {"extra_roots": "", "allow_any_path": False},
                "public_tools_allow_high": False,
            }
        return {
            "ok": True,
            "from_db": True,
            "policy": row,
            "public_tools_allow_high": bool(row.get("allow_high_risk_public_tools")),
        }

    @router.post("/admin/api/users/workspace-path-policy")
    def api_users_workspace_path_policy_save(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        wmode = _workspace_path_policy_write_mode(ctx)
        if wmode is None:
            raise HTTPException(status_code=403, detail="forbidden")
        tid = str(payload.get("tenant_id") or "").strip()
        uid = str(payload.get("user_id") or "").strip()
        _require_tenant_scope(ctx, tid)
        if not tid or not uid:
            return {"ok": False, "error": "tenant_id and user_id are required"}
        if wmode == "self" and (tid != str(ctx.get("tenant_id") or "") or uid != str(ctx.get("user_id") or "")):
            raise HTTPException(status_code=403, detail="workspace_paths_self_only")
        if not store.get_user_by_id(tenant_id=tid, user_id=uid):
            return {"ok": False, "error": "user_not_found"}
        extra_raw = str(payload.get("extra_roots") or "")
        norm, err = _normalize_workspace_extra_roots(extra_raw)
        if err:
            return {"ok": False, "error": err}
        allow_any = bool(payload.get("allow_any_path", False))
        allow_high = bool(payload.get("public_tools_allow_high", False))
        store.upsert_user_workspace_path_allowlist(
            tenant_id=tid,
            user_id=uid,
            extra_roots=norm,
            allow_any_path=allow_any,
            allow_high_risk_public_tools=allow_high,
        )
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="user_workspace_path_policy_save",
            target_type="user",
            target_id=uid,
            status="ok",
            detail={
                "tenant_id": tid,
                "allow_any_path": allow_any,
                "public_tools_allow_high": bool(allow_high),
                "extra_roots_preview": norm[:500],
            },
        )
        row = store.get_user_workspace_path_allowlist(tenant_id=tid, user_id=uid)
        return {"ok": True, "policy": row or {}, "public_tools_allow_high": bool((row or {}).get("allow_high_risk_public_tools"))}

    @router.post("/admin/api/users/delete-unbound")
    def api_users_delete_unbound(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:delete")
        tenant_id = str(payload.get("tenant_id") or "").strip()
        _require_tenant_scope(ctx, tenant_id)
        channel = str(payload.get("channel") or "wecom").strip() or "wecom"
        if not tenant_id:
            return {"ok": False, "error": "tenant_id is required"}
        users = store.list_users(tenant_id=tenant_id, limit=5000)
        if str(channel).strip().lower() == "wecom":
            binds = store.list_channel_identities_v2(tenant_id=tenant_id, channel=channel, limit=5000)
        else:
            binds = store.list_channel_identities(tenant_id=tenant_id, channel=channel, limit=5000)
        bound_user_ids = {str(b.get("user_id") or "") for b in binds}
        orphan_ids = [
            str(u.get("id") or "")
            for u in users
            if str(u.get("id") or "") not in bound_user_ids
            and str(u.get("username") or "").strip().lower() != "administrator"
        ]
        deleted = 0
        if orphan_ids:
            with store._connect() as conn:
                for uid in orphan_ids:
                    cur = conn.execute(
                        "DELETE FROM app_user WHERE tenant_id = ? AND id = ?",
                        (tenant_id, uid),
                    )
                    deleted += int(cur.rowcount or 0)
        return {
            "ok": True,
            "deleted": deleted,
            "users_total": len(users),
            "bound_users": len([x for x in bound_user_ids if x]),
            "orphan_users": len(orphan_ids),
        }

    @router.get("/admin/api/bind-codes")
    def api_bind_codes(tenant_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:read")
        _require_tenant_scope(ctx, tenant_id)
        rows = store.list_bind_codes(tenant_id=tenant_id, limit=200)
        return {"ok": True, "codes": rows}

    @router.post("/admin/api/bind-codes/create")
    def api_bind_codes_create(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:write")
        tenant_id = str(payload.get("tenant_id") or "").strip()
        _require_tenant_scope(ctx, tenant_id)
        role = str(payload.get("role") or "member").strip() or "member"
        if not tenant_id:
            return {"ok": False, "error": "tenant_id is required"}
        code = str(payload.get("code") or "").strip() or secrets.token_urlsafe(6)
        row = store.create_bind_code(tenant_id=tenant_id, role=role, code=code)
        return {"ok": True, "code": row}

    @router.post("/admin/api/bind-codes/delete")
    def api_bind_codes_delete(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:write")
        tenant_id = str(payload.get("tenant_id") or "").strip()
        _require_tenant_scope(ctx, tenant_id)
        code = str(payload.get("code") or "").strip()
        if not tenant_id:
            return {"ok": False, "error": "tenant_id is required"}
        if not code:
            return {"ok": False, "error": "code is required"}
        with store._connect() as conn:
            cur = conn.execute(
                "DELETE FROM bind_code WHERE tenant_id = ? AND code = ?",
                (tenant_id, code),
            )
            deleted = int(cur.rowcount or 0)
        return {"ok": True, "deleted": deleted}

    @router.get("/admin/api/wecom/config")
    def api_wecom_config(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        return {
            "ok": True,
            "config": {
                "wecom_mode": "bot_api",
                "wecom_bot_id": str(store.get_setting("wecom_bot_id") or ""),
                "wecom_bot_secret": str(store.get_secret("wecom_bot_secret") or ""),
                "wecom_auto_bind_enabled": str(store.get_setting("wecom_auto_bind_enabled") or "1"),
                "wecom_auto_bind_tenant_name": str(store.get_setting("wecom_auto_bind_tenant_name") or "Team"),
                "wecom_auto_bind_role": str(store.get_setting("wecom_auto_bind_role") or "member"),
            },
        }

    @router.get("/admin/api/wecom/health")
    def api_wecom_health(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        svc = next((s for s in status_services() if str(s.name) == "channel:wecom"), None)
        def _gs(k: str) -> str:
            return str(store.get_setting(k) or "").strip()
        recent_raw = _gs("wecom_recent_from_users")
        try:
            recent = json.loads(recent_raw) if recent_raw else []
            if not isinstance(recent, list):
                recent = []
        except Exception:
            recent = []
        return {
            "ok": True,
            "service": {
                "name": "channel:wecom",
                "running": bool(getattr(svc, "running", False)) if svc else False,
                "pid": int(getattr(svc, "pid", 0) or 0) if svc else 0,
            },
            "inbound": {
                "last_msg_ts": _gs("wecom_last_msg_ts"),
                "last_from_user": _gs("wecom_last_from_user"),
                "recent_from_users": recent[:20],
                "last_cmd": _gs("wecom_last_cmd"),
                "last_parse_error": _gs("wecom_last_parse_error"),
            },
            "outbound": {
                "last_mode": _gs("wecom_last_outbound_mode"),
                "last_error": _gs("wecom_last_outbound_error"),
                "last_ack_req_id": _gs("wecom_last_ack_req_id"),
                "last_ack_errcode": _gs("wecom_last_ack_errcode"),
                "last_ack_errmsg": _gs("wecom_last_ack_errmsg"),
            },
            "raw": {
                "last_raw_from_user": _gs("wecom_last_raw_from_user"),
                "last_raw_body": _gs("wecom_last_raw_body"),
                "last_unknown_cmd_payload": _gs("wecom_last_unknown_cmd_payload"),
            },
        }

    @router.post("/admin/api/wecom/config")
    def api_wecom_config_save(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        store.set_setting("wecom_mode", "bot_api")
        store.set_setting("wecom_bot_id", str(payload.get("wecom_bot_id") or "").strip())
        bot_secret = str(payload.get("wecom_bot_secret") or "").strip()
        if bot_secret:
            store.set_secret("wecom_bot_secret", bot_secret)
        auto_enabled = str(payload.get("wecom_auto_bind_enabled") or "").strip().lower()
        enabled_truthy = auto_enabled in ("1", "true", "yes", "on")
        store.set_setting("wecom_auto_bind_enabled", "1" if enabled_truthy else "0")
        store.set_setting(
            "wecom_auto_bind_tenant_name",
            str(payload.get("wecom_auto_bind_tenant_name") or "").strip() or "Team",
        )
        store.set_setting(
            "wecom_auto_bind_role",
            str(payload.get("wecom_auto_bind_role") or "").strip() or "member",
        )
        return api_wecom_config()

    @router.post("/admin/api/wecom/unbind")
    def api_wecom_unbind(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        with store._connect() as conn:
            cur_ident = conn.execute("DELETE FROM channel_identity WHERE channel = ?", ("wecom",))
            ident_deleted = int(cur_ident.rowcount or 0)
            cur_sess = conn.execute("DELETE FROM channel_session WHERE channel = ?", ("wecom",))
            sess_deleted = int(cur_sess.rowcount or 0)
        for k in _WECOM_CLEAR_KEYS:
            store.delete_setting(k)
        with store._connect() as conn:
            conn.execute(
                "DELETE FROM app_setting WHERE key LIKE 'wecom:bot_secret:%' OR key LIKE 'wecom:agent_secret:%'"
            )
        cfg = api_wecom_config()
        return {
            "ok": True,
            "deleted_channel_identity": ident_deleted,
            "deleted_channel_session": sess_deleted,
            "config": cfg.get("config", {}),
        }

    @router.get("/admin/api/audit")
    def api_audit(
        session_id: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        rows = store.list_agent_audit_logs(limit=200, session_id=session_id)
        return {"ok": True, "audit": rows}

    @router.get("/admin/api/audit/session-health")
    def api_audit_session_health(
        session_id: str | None = Query(default=None),
        limit: int = Query(default=80),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        rows = store.list_session_tool_health(session_id=session_id, limit=limit)
        warn = [x for x in rows if str(x.get("status") or "") == "warn_no_tool_calls"]
        return {"ok": True, "items": rows, "warn_count": len(warn)}

    @router.get("/admin/api/trace")
    def api_trace(
        session_id: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        if not session_id:
            return {"ok": True, "trace": []}
        rows = store.list_trace_events(session_id=session_id, limit=300)
        return {"ok": True, "trace": rows}

    @router.get("/admin/api/oclaw/tasks")
    @router.get("/admin/api/oclaw/tasks")
    def api_oclaw_tasks(
        task_id: str | None = Query(default=None),
        session_id: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=80),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        tenant_id = str(ctx.get("tenant_id") or "")
        sid = str(session_id or "").strip() or None
        st = str(status or "").strip() or None
        if task_id:
            task = store.oclaw_task_get(task_id=str(task_id), tenant_id=tenant_id)
            return {"ok": True, "task": None if not task else task.__dict__}
        rows = store.oclaw_task_list(
            status=st,
            session_id=sid,
            tenant_id=tenant_id,
            limit=max(1, min(int(limit or 80), 300)),
        )
        by_status: dict[str, int] = {"queued": 0, "claimed": 0, "done": 0, "failed": 0}
        for r in rows:
            s = str(r.status or "")
            by_status[s] = int(by_status.get(s, 0)) + 1
        return {"ok": True, "tasks": [r.__dict__ for r in rows], "counts": by_status}

    @router.get("/admin/api/oclaw/runs")
    @router.get("/admin/api/oclaw/runs")
    def api_oclaw_runs(
        run_id: str | None = Query(default=None),
        session_id: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=80),
        include_attempts: int = Query(default=1),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        tenant_id = str(ctx.get("tenant_id") or "")
        if run_id:
            row = store.oclaw_run_get(run_id=str(run_id), tenant_id=tenant_id)
            if not row:
                return {"ok": True, "run": None}
            out = dict(row.__dict__)
            if int(include_attempts or 0):
                out["attempts"] = store.oclaw_attempt_list(run_id=row.run_id, limit=50)
            return {"ok": True, "run": out}
        rows = store.oclaw_run_list(
            tenant_id=tenant_id,
            session_id=str(session_id or "").strip() or None,
            status=str(status or "").strip() or None,
            limit=max(1, min(int(limit or 80), 300)),
        )
        by_status: dict[str, int] = {"running": 0, "success": 0, "failed": 0}
        out_rows = []
        for r in rows:
            s = str(r.status or "")
            by_status[s] = int(by_status.get(s, 0)) + 1
            item = dict(r.__dict__)
            if int(include_attempts or 0):
                item["attempts"] = store.oclaw_attempt_list(run_id=r.run_id, limit=20)
            out_rows.append(item)
        configured_retryable = sorted(resolve_retryable_error_codes(store=store))
        return {
            "ok": True,
            "runs": out_rows,
            "counts": by_status,
            "retry_policy": {
                "setting_key": "AIA_OCLAW_RETRYABLE_ERROR_CODES",
                "effective_retryable_error_codes": configured_retryable,
                "default_retryable_error_codes": list(DEFAULT_RETRYABLE_ERROR_CODES),
            },
        }

    @router.get("/admin/api/replay/turn")
    def api_replay_turn(
        session_id: str,
        trace_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """Return a best-effort replay bundle for a single turn (trace_id)."""
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        sid = str(session_id or "").strip()
        tid = str(trace_id or "").strip()
        if not sid or not tid:
            return {"ok": False, "error": "session_id_and_trace_id_required"}
        # Restrict non-administrator users to their own sessions only.
        uname = str(ctx.get("username") or "").strip().lower()
        if uname != "administrator":
            # Must be owned by current user in current tenant.
            owner = store.get_session_for_user(
                session_id=sid, tenant_id=str(ctx.get("tenant_id") or ""), user_id=str(ctx.get("user_id") or "")
            )
            if not owner:
                raise HTTPException(status_code=403, detail="forbidden")

        trace_rows = store.list_trace_events_for_trace(session_id=sid, trace_id=tid, limit=800)
        start_ts, end_ts = store.get_turn_time_window(session_id=sid, trace_id=tid)
        msgs = store.list_messages_in_time_window(session_id=sid, start_ts=start_ts, end_ts=end_ts, limit=1200)
        def _to_ms(v: Any) -> int | None:
            s = str(v or "").strip()
            if not s:
                return None
            try:
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                return int(datetime.fromisoformat(s).timestamp() * 1000)
            except Exception:
                return None

        ws_accepted_ms: int | None = None
        gateway_received_ms: int | None = None
        model_chat_start_ms: int | None = None
        ws_first_token_ms: int | None = None
        for row in trace_rows or []:
            if not isinstance(row, dict):
                continue
            event_type = str(row.get("event_type") or "").strip()
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            row_ts = _to_ms(row.get("timestamp"))
            if event_type == "gateway_received":
                gateway_received_ms = row_ts if row_ts is not None else gateway_received_ms
                if ws_accepted_ms is None:
                    try:
                        v = payload.get("ws_client_send_ms")
                        if v is not None:
                            ws_accepted_ms = int(v)
                    except Exception:
                        pass
            elif event_type == "model_chat_start":
                model_chat_start_ms = row_ts if row_ts is not None else model_chat_start_ms
            elif event_type == "ws_first_token":
                if ws_first_token_ms is None:
                    try:
                        vft = payload.get("ws_first_token_ms")
                        if vft is not None:
                            ws_first_token_ms = int(vft)
                    except Exception:
                        pass
                if ws_accepted_ms is None:
                    try:
                        va = payload.get("ws_accepted_ms")
                        if va is not None:
                            ws_accepted_ms = int(va)
                    except Exception:
                        pass
                if ws_first_token_ms is None:
                    ws_first_token_ms = row_ts if row_ts is not None else ws_first_token_ms

        def _delta(a: int | None, b: int | None) -> int | None:
            if a is None or b is None:
                return None
            d = int(b - a)
            return d if d >= 0 else None

        ttft = {
            "ws_accepted_ms": ws_accepted_ms,
            "gateway_received_ms": gateway_received_ms,
            "model_chat_start_ms": model_chat_start_ms,
            "ws_first_token_ms": ws_first_token_ms,
            "accepted_to_gateway_ms": _delta(ws_accepted_ms, gateway_received_ms),
            "gateway_to_model_start_ms": _delta(gateway_received_ms, model_chat_start_ms),
            "model_start_to_first_token_ms": _delta(model_chat_start_ms, ws_first_token_ms),
            "gateway_to_first_token_ms": _delta(gateway_received_ms, ws_first_token_ms),
            "accepted_to_first_token_ms": _delta(ws_accepted_ms, ws_first_token_ms),
        }
        return {
            "ok": True,
            "session_id": sid,
            "trace_id": tid,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "ttft": ttft,
            "trace": trace_rows,
            "messages": msgs,
        }

    @router.get("/admin/api/plugins")
    def api_plugins(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:write")
        rows = store.list_tool_plugins()
        return {"ok": True, "plugins": rows}

    @router.get("/admin/api/tool-policy")
    def api_tool_policy(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        # Oclaw takeover: legacy tool-policy switches are disconnected (kept in DB for later).
        disabled = False
        retry_mode = "first_round_only"
        loop_state_machine = True
        signature_budget = 2
        tmw_raw = str(store.get_setting("AIA_TURN_MAX_TOOL_WORKERS") or "").strip()
        tmr_raw = str(store.get_setting("AIA_TURN_MAX_TOOL_ROUNDS") or "").strip()
        tmc_raw = str(store.get_setting("AIA_TURN_MAX_CONTEXT_MESSAGES") or "").strip()
        turn_max_tool_workers = max(1, min(int(tmw_raw), 32)) if tmw_raw.isdigit() else 8
        turn_max_tool_rounds = max(1, min(int(tmr_raw), 30)) if tmr_raw.isdigit() else 8
        turn_max_context_messages = max(10, min(int(tmc_raw), 400)) if tmc_raw.isdigit() else 80
        # Oclaw takeover: legacy runner switches are disconnected (kept in DB for later).
        turn_runner_impl = "oclaw"
        # Oclaw takeover: legacy manager decision mode is disconnected (kept in DB for later).
        manager_decision_mode = ""
        sse_raw = str(store.get_setting("AIA_SSE_QUEUE_MAXSIZE") or "").strip()
        sse_queue_maxsize = max(200, min(int(sse_raw), 50_000)) if sse_raw.isdigit() else 2000
        tl_raw = str(store.get_setting("AIA_TOOL_LOG_MAX_CHARS") or "").strip()
        tool_log_max_chars = max(20_000, min(int(tl_raw), 2_000_000)) if tl_raw.isdigit() else 200_000
        emcp_raw = str(store.get_setting("AIA_ENABLE_MCP_TOOLS") or "").strip().lower()
        enable_mcp_tools = emcp_raw not in ("0", "false", "no", "off")
        epl_raw = str(store.get_setting("AIA_ENABLE_PLUGIN_TOOLS") or "").strip().lower()
        enable_plugin_tools = epl_raw in ("1", "true", "yes", "on")
        erc_raw = str(store.get_setting("AIA_ENABLE_RUN_COMMAND") or "").strip().lower()
        enable_run_command = erc_raw not in ("0", "false", "no", "off")
        tctx_raw = str(store.get_setting("AIA_TOOL_CONTEXT_TRUNCATE_ENABLED") or "").strip().lower()
        tool_context_truncate_enabled = tctx_raw not in ("0", "false", "no", "off")
        ttft_raw = str(store.get_setting("AIA_CHAT_SHOW_TTFT_DEBUG") or "").strip().lower()
        # default OFF (release-safe): only enabled when explicitly set truthy.
        chat_show_ttft_debug = ttft_raw in ("1", "true", "yes", "on")
        skl_raw = str(store.get_setting("AIA_SKILL_RUNTIME_ENABLED") or "").strip().lower()
        skill_runtime_enabled = skl_raw not in ("0", "false", "no", "off")
        sai_raw = str(store.get_setting("AIA_SKILL_AUTO_INSTALL_ENABLED") or "").strip().lower()
        skill_auto_install_enabled = sai_raw not in ("0", "false", "no", "off")
        tmsg_raw = str(store.get_setting("AIA_TOOL_LLM_MESSAGE_MAX_CHARS") or "").strip()
        if tmsg_raw.isdigit():
            _n = int(tmsg_raw)
            tool_llm_message_max_chars = 0 if _n == 0 else max(4096, min(_n, 500_000))
        else:
            tool_llm_message_max_chars = 0
        mcp_fs_raw = str(store.get_setting("AIA_MCP_FILESYSTEM_EXTRA_ROOTS") or "").strip()
        mcp_env_allow_raw = str(store.get_setting("AIA_MCP_ENV_ALLOWLIST") or "").strip()
        retry_codes_raw = str(store.get_setting("AIA_OCLAW_RETRYABLE_ERROR_CODES") or "").strip()
        if not retry_codes_raw:
            retry_codes_raw = ",".join(DEFAULT_RETRYABLE_ERROR_CODES)
        retry_strict_raw = str(store.get_setting("AIA_OCLAW_RETRY_CODES_STRICT_MODE") or "").strip().lower()
        retry_codes_strict_mode = retry_strict_raw in ("1", "true", "yes", "on")
        wc_workers_raw = str(store.get_setting("AIA_WECOM_LONGCONN_WORKERS") or "").strip()
        if not wc_workers_raw:
            wc_workers_raw = str(store.get_setting("WECOM_LONGCONN_WORKERS") or "").strip()
        wc_in_q_raw = str(store.get_setting("AIA_WECOM_LONGCONN_INBOUND_QUEUE_MAXSIZE") or "").strip()
        if not wc_in_q_raw:
            wc_in_q_raw = str(store.get_setting("WECOM_LONGCONN_INBOUND_QUEUE_MAXSIZE") or "").strip()
        wecom_longconn_workers = max(1, min(int(wc_workers_raw), 8)) if wc_workers_raw.isdigit() else 2
        wecom_longconn_inbound_queue_maxsize = max(20, min(int(wc_in_q_raw), 5000)) if wc_in_q_raw.isdigit() else 200
        return {
            "ok": True,
            "disable_tool_confirm": disabled,
            "enforced_retry_mode": retry_mode,
            "tool_loop_state_machine": loop_state_machine,
            "tool_signature_budget": signature_budget,
            "turn_max_tool_workers": turn_max_tool_workers,
            "turn_max_tool_rounds": turn_max_tool_rounds,
            "turn_max_context_messages": turn_max_context_messages,
            "turn_runner_impl": turn_runner_impl,
            "manager_decision_mode": manager_decision_mode,
            "sse_queue_maxsize": sse_queue_maxsize,
            "tool_log_max_chars": tool_log_max_chars,
            "enable_mcp_tools": enable_mcp_tools,
            "enable_plugin_tools": enable_plugin_tools,
            "enable_run_command": enable_run_command,
            "tool_context_truncate_enabled": tool_context_truncate_enabled,
            "chat_show_ttft_debug": chat_show_ttft_debug,
            "skill_runtime_enabled": skill_runtime_enabled,
            "skill_auto_install_enabled": skill_auto_install_enabled,
            "tool_llm_message_max_chars": tool_llm_message_max_chars,
            "mcp_filesystem_extra_roots": mcp_fs_raw,
            "mcp_env_allowlist": mcp_env_allow_raw,
            "oclaw_retryable_error_codes": retry_codes_raw,
            "oclaw_retry_codes_strict_mode": retry_codes_strict_mode,
            "wecom_longconn_workers": wecom_longconn_workers,
            "wecom_longconn_inbound_queue_maxsize": wecom_longconn_inbound_queue_maxsize,
        }

    @router.post("/admin/api/tool-policy")
    def api_tool_policy_save(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        # Oclaw takeover: legacy tool-policy switches are disconnected (kept in DB for later).
        disable_confirm = False
        retry_mode = "first_round_only"
        sm = True
        sig_budget_n = 2
        tmw = payload.get("turn_max_tool_workers", 8)
        tmr = payload.get("turn_max_tool_rounds", 8)
        tmc = payload.get("turn_max_context_messages", 80)
        tri = "oclaw"
        try:
            tmw_n = max(1, min(int(tmw), 32))
        except Exception:
            tmw_n = 8
        try:
            tmr_n = max(1, min(int(tmr), 30))
        except Exception:
            tmr_n = 8
        try:
            tmc_n = max(10, min(int(tmc), 400))
        except Exception:
            tmc_n = 80
        md = ""
        sse_q = payload.get("sse_queue_maxsize", 2000)
        tl_cap = payload.get("tool_log_max_chars", 200000)
        try:
            sse_q_n = max(200, min(int(sse_q), 50_000))
        except Exception:
            sse_q_n = 2000
        try:
            tl_cap_n = max(20_000, min(int(tl_cap), 2_000_000))
        except Exception:
            tl_cap_n = 200_000
        emcp = bool(payload.get("enable_mcp_tools", True))
        epl = bool(payload.get("enable_plugin_tools", False))
        erc = bool(payload.get("enable_run_command", True))
        tctx = bool(payload.get("tool_context_truncate_enabled", True))
        ttft_debug = bool(payload.get("chat_show_ttft_debug", False))
        skl_rt = bool(payload.get("skill_runtime_enabled", True))
        skl_ai = bool(payload.get("skill_auto_install_enabled", True))
        tmsg = payload.get("tool_llm_message_max_chars", 0)
        mcp_fs_roots = str(payload.get("mcp_filesystem_extra_roots") or "").strip()
        mcp_env_allow = str(payload.get("mcp_env_allowlist") or "").strip()
        retry_codes = str(payload.get("oclaw_retryable_error_codes") or "").strip()
        retry_codes_strict_mode = bool(payload.get("oclaw_retry_codes_strict_mode", False))
        unknown_retry_codes: list[str] = []
        if retry_codes:
            vals = [x.strip().lower() for x in retry_codes.split(",") if x and x.strip()]
            allowed = set(ALL_ATTEMPT_ERROR_CODES)
            known_vals: list[str] = []
            for x in vals:
                if x in allowed:
                    known_vals.append(x)
                else:
                    unknown_retry_codes.append(x)
            # dedupe while preserving order
            seen: set[str] = set()
            kept = []
            for x in known_vals:
                if x in seen:
                    continue
                seen.add(x)
                kept.append(x)
            retry_codes = ",".join(kept)
        else:
            retry_codes = ",".join(DEFAULT_RETRYABLE_ERROR_CODES)
        if retry_codes_strict_mode and unknown_retry_codes:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_retryable_error_codes",
                    "message": "Unknown oclaw retryable error codes",
                    "unknown_retryable_error_codes": unknown_retry_codes,
                    "allowed_retryable_error_codes": list(ALL_ATTEMPT_ERROR_CODES),
                },
            )
        if not retry_codes:
            retry_codes = ",".join(DEFAULT_RETRYABLE_ERROR_CODES)
        wc_workers = payload.get("wecom_longconn_workers", 2)
        wc_in_q = payload.get("wecom_longconn_inbound_queue_maxsize", 200)
        try:
            _tn = int(tmsg)
            tmsg_n = 0 if _tn == 0 else max(4096, min(_tn, 500_000))
        except Exception:
            tmsg_n = 0
        try:
            wc_workers_n = max(1, min(int(wc_workers), 8))
        except Exception:
            wc_workers_n = 2
        try:
            wc_in_q_n = max(20, min(int(wc_in_q), 5000))
        except Exception:
            wc_in_q_n = 200
        # Canonical professional prefix.
        # Legacy-only (disconnected): do not write the following settings:
        # - AIA_DISABLE_TOOL_CONFIRM
        # - AIA_TOOL_ENFORCED_RETRY_MODE
        # - AIA_TOOL_LOOP_STATE_MACHINE
        # - AIA_TOOL_SIGNATURE_BUDGET
        store.set_setting("AIA_TURN_MAX_TOOL_WORKERS", str(tmw_n))
        store.set_setting("AIA_TURN_MAX_TOOL_ROUNDS", str(tmr_n))
        store.set_setting("AIA_TURN_MAX_CONTEXT_MESSAGES", str(tmc_n))
        # Legacy-only (disconnected): do not write AIA_MANAGER_DECISION_MODE here.
        store.set_setting("AIA_SSE_QUEUE_MAXSIZE", str(sse_q_n))
        store.set_setting("AIA_TOOL_LOG_MAX_CHARS", str(tl_cap_n))
        store.set_setting("AIA_ENABLE_MCP_TOOLS", "1" if emcp else "0")
        store.set_setting("AIA_ENABLE_PLUGIN_TOOLS", "1" if epl else "0")
        store.set_setting("AIA_ENABLE_RUN_COMMAND", "1" if erc else "0")
        # Keep runtime gate aligned with Admin toggle immediately.
        os.environ["AIA_ENABLE_RUN_COMMAND"] = "1" if erc else "0"
        store.set_setting("AIA_TOOL_CONTEXT_TRUNCATE_ENABLED", "1" if tctx else "0")
        store.set_setting("AIA_CHAT_SHOW_TTFT_DEBUG", "1" if ttft_debug else "0")
        store.set_setting("AIA_SKILL_RUNTIME_ENABLED", "1" if skl_rt else "0")
        store.set_setting("AIA_SKILL_AUTO_INSTALL_ENABLED", "1" if skl_ai else "0")
        store.set_setting("AIA_TOOL_LLM_MESSAGE_MAX_CHARS", str(tmsg_n))
        store.set_setting("AIA_MCP_FILESYSTEM_EXTRA_ROOTS", mcp_fs_roots)
        store.set_setting("AIA_MCP_ENV_ALLOWLIST", mcp_env_allow)
        store.set_setting("AIA_OCLAW_RETRYABLE_ERROR_CODES", retry_codes)
        store.set_setting("AIA_OCLAW_RETRY_CODES_STRICT_MODE", "1" if retry_codes_strict_mode else "0")
        store.set_setting("AIA_WECOM_LONGCONN_WORKERS", str(wc_workers_n))
        store.set_setting("AIA_WECOM_LONGCONN_INBOUND_QUEUE_MAXSIZE", str(wc_in_q_n))
        store.set_setting("WECOM_LONGCONN_WORKERS", str(wc_workers_n))
        store.set_setting("WECOM_LONGCONN_INBOUND_QUEUE_MAXSIZE", str(wc_in_q_n))
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="tool_policy_update",
            target_type="tool_policy",
            target_id="AIA_TURN_MAX_TOOL_WORKERS,AIA_TURN_MAX_TOOL_ROUNDS,AIA_TURN_MAX_CONTEXT_MESSAGES,AIA_SSE_QUEUE_MAXSIZE,AIA_TOOL_LOG_MAX_CHARS,AIA_ENABLE_MCP_TOOLS,AIA_ENABLE_PLUGIN_TOOLS,AIA_ENABLE_RUN_COMMAND,AIA_TOOL_CONTEXT_TRUNCATE_ENABLED,AIA_CHAT_SHOW_TTFT_DEBUG,AIA_SKILL_RUNTIME_ENABLED,AIA_SKILL_AUTO_INSTALL_ENABLED,AIA_TOOL_LLM_MESSAGE_MAX_CHARS,AIA_MCP_FILESYSTEM_EXTRA_ROOTS,AIA_MCP_ENV_ALLOWLIST,AIA_OCLAW_RETRYABLE_ERROR_CODES,AIA_OCLAW_RETRY_CODES_STRICT_MODE,AIA_WECOM_LONGCONN_WORKERS,AIA_WECOM_LONGCONN_INBOUND_QUEUE_MAXSIZE",
            status="ok",
            detail={
                "disable_tool_confirm": disable_confirm,
                "enforced_retry_mode": retry_mode,
                "tool_loop_state_machine": sm,
                "tool_signature_budget": sig_budget_n,
                "turn_max_tool_workers": tmw_n,
                "turn_max_tool_rounds": tmr_n,
                "turn_max_context_messages": tmc_n,
                "turn_runner_impl": tri,
                "manager_decision_mode": md,
                "sse_queue_maxsize": sse_q_n,
                "tool_log_max_chars": tl_cap_n,
                "enable_mcp_tools": emcp,
                "enable_plugin_tools": epl,
                "enable_run_command": erc,
                "tool_context_truncate_enabled": tctx,
                "chat_show_ttft_debug": ttft_debug,
                "skill_runtime_enabled": skl_rt,
                "skill_auto_install_enabled": skl_ai,
                "tool_llm_message_max_chars": tmsg_n,
                "mcp_filesystem_extra_roots": mcp_fs_roots,
                "mcp_env_allowlist": mcp_env_allow,
                "oclaw_retryable_error_codes": retry_codes,
                "oclaw_retry_codes_strict_mode": retry_codes_strict_mode,
                "unknown_retryable_error_codes": unknown_retry_codes,
                "wecom_longconn_workers": wc_workers_n,
                "wecom_longconn_inbound_queue_maxsize": wc_in_q_n,
            },
        )
        return {
            "ok": True,
            "disable_tool_confirm": disable_confirm,
            "enforced_retry_mode": retry_mode,
            "tool_loop_state_machine": sm,
            "tool_signature_budget": sig_budget_n,
            "turn_max_tool_workers": tmw_n,
            "turn_max_tool_rounds": tmr_n,
            "turn_max_context_messages": tmc_n,
            "turn_runner_impl": tri,
            "manager_decision_mode": md,
            "sse_queue_maxsize": sse_q_n,
            "tool_log_max_chars": tl_cap_n,
            "enable_mcp_tools": emcp,
            "enable_plugin_tools": epl,
            "enable_run_command": erc,
            "tool_context_truncate_enabled": tctx,
            "chat_show_ttft_debug": ttft_debug,
            "skill_runtime_enabled": skl_rt,
            "skill_auto_install_enabled": skl_ai,
            "tool_llm_message_max_chars": tmsg_n,
            "mcp_filesystem_extra_roots": mcp_fs_roots,
            "mcp_env_allowlist": mcp_env_allow,
            "oclaw_retryable_error_codes": retry_codes,
            "oclaw_retry_codes_strict_mode": retry_codes_strict_mode,
            "unknown_retryable_error_codes": unknown_retry_codes,
            "wecom_longconn_workers": wc_workers_n,
            "wecom_longconn_inbound_queue_maxsize": wc_in_q_n,
        }

    @router.get("/admin/api/mcp/servers")
    def api_mcp_servers(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        rows = McpRegistry(store).list_servers(enabled_only=False)
        health = {str(x.get("server_id") or ""): x for x in store.list_mcp_server_health()}
        for r in rows:
            sid = str(r.get("server_id") or "")
            r["health"] = health.get(sid) or {}
            r["tools"] = store.list_mcp_server_tools(server_id=sid)
        return {"ok": True, "servers": rows}

    @router.get("/admin/api/mcp/export")
    def api_mcp_export(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        return {
            "ok": True,
            "local_path": str(mcp_migrated_json_path()),
            "document": build_mcp_install_export_document(store),
        }

    @router.get("/admin/api/mcp/failures")
    def api_mcp_failures(
        limit: int = Query(default=20),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        return {"ok": True, "items": store.list_mcp_install_failure_summary(limit=limit)}

    @router.get("/admin/api/mcp/usage")
    def api_mcp_usage(
        server_id: str | None = Query(default=None),
        limit: int = Query(default=200),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        return {
            "ok": True,
            "summary": store.list_mcp_tool_usage_summary(limit=limit),
            "calls": store.list_mcp_tool_call_logs(server_id=server_id, limit=limit),
        }

    @router.get("/admin/api/mcp/tool-wire")
    def api_mcp_tool_wire_get(
        role: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        from oclaw.platform.llm.tool_wire_policy import build_tool_wire_snapshot

        return build_tool_wire_snapshot(store, role=str(role or "").strip().lower() or None)

    @router.post("/admin/api/mcp/tool-wire/config")
    def api_mcp_tool_wire_config_save(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        from oclaw.platform.llm.tool_wire_policy import SETTINGS_KEY_ADMIN_CONFIG, load_merged_admin_config

        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        raw = store.get_setting(SETTINGS_KEY_ADMIN_CONFIG)
        cur: dict[str, Any] = {}
        if raw:
            try:
                cur = json.loads(raw) if isinstance(raw, str) else {}
            except Exception:
                cur = {}
        if not isinstance(cur, dict):
            cur = {}
        if "wire_policy" in payload:
            wp = str(payload.get("wire_policy") or "").strip().lower()
            if wp in ("inherit", "always", "never"):
                cur["wire_policy"] = wp
        if "top_n_full" in payload:
            cur["top_n_full"] = max(3, min(80, int(payload.get("top_n_full") or 20)))
        if "stale_hours" in payload:
            cur["stale_hours"] = max(0.25, min(720.0, float(payload.get("stale_hours") or 3)))
        if "penalty_minutes" in payload:
            cur["penalty_minutes"] = max(1.0, min(24 * 60, float(payload.get("penalty_minutes") or 30)))
        if "medium_rank_start" in payload:
            cur["medium_rank_start"] = int(payload.get("medium_rank_start") or 21)
        if "medium_rank_end" in payload:
            cur["medium_rank_end"] = int(payload.get("medium_rank_end") or 50)
        if "medium_desc_chars" in payload:
            cur["medium_desc_chars"] = max(80, min(4000, int(payload.get("medium_desc_chars") or 520)))
        if "minimal_desc_cap" in payload:
            cur["minimal_desc_cap"] = max(0, min(2000, int(payload.get("minimal_desc_cap") or 80)))
        if "penalty_disable" in payload:
            cur["penalty_disable"] = bool(payload.get("penalty_disable"))
        store.set_setting(SETTINGS_KEY_ADMIN_CONFIG, json.dumps(cur, ensure_ascii=False))
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_tool_wire_config_update",
            target_type="app_setting",
            target_id=SETTINGS_KEY_ADMIN_CONFIG,
            status="ok",
            detail={"keys": list(cur.keys())},
        )
        return {"ok": True, "config": load_merged_admin_config(store)}

    @router.post("/admin/api/mcp/tool-wire/role-mode")
    def api_mcp_tool_wire_role_mode_save(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        from oclaw.platform.llm.tool_wire_policy import SETTINGS_KEY_ROLE_MODE_BY_ROLE

        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        role = str(payload.get("role") or "").strip().lower()
        if not role:
            raise HTTPException(status_code=400, detail="role_required")
        valid_roles = set(_ordered_mcp_roles())
        if role not in valid_roles:
            raise HTTPException(status_code=400, detail="invalid_role")
        mode = str(payload.get("mode") or "").strip().lower()
        if mode not in {"restricted", "unrestricted", "forbidden"}:
            raise HTTPException(status_code=400, detail="invalid_mode")
        raw = str(store.get_setting(SETTINGS_KEY_ROLE_MODE_BY_ROLE) or "").strip() or "{}"
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {}
        if not isinstance(obj, dict):
            obj = {}
        obj[role] = mode
        store.set_setting(SETTINGS_KEY_ROLE_MODE_BY_ROLE, json.dumps(obj, ensure_ascii=False))
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_tool_wire_role_mode_update",
            target_type="app_setting",
            target_id=f"{SETTINGS_KEY_ROLE_MODE_BY_ROLE}:{role}",
            status="ok",
            detail={"role": role, "mode": mode},
        )
        return {"ok": True, "role": role, "mode": mode}

    @router.post("/admin/api/mcp/tool-wire/penalty/reset")
    def api_mcp_tool_wire_penalty_reset(
        role: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        from oclaw.platform.llm.tool_wire_policy import SETTINGS_KEY_PENALTY_STATE, SETTINGS_KEY_PENALTY_STATE_BY_ROLE

        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        r = str(role or "").strip().lower()
        if not r:
            store.set_setting(SETTINGS_KEY_PENALTY_STATE, "{}")
            target_id = SETTINGS_KEY_PENALTY_STATE
        else:
            # Reset only one role's penalty bucket.
            raw = str(store.get_setting(SETTINGS_KEY_PENALTY_STATE_BY_ROLE) or "").strip() or "{}"
            try:
                obj = json.loads(raw)
            except Exception:
                obj = {}
            if not isinstance(obj, dict):
                obj = {}
            obj[r] = {}
            store.set_setting(SETTINGS_KEY_PENALTY_STATE_BY_ROLE, json.dumps(obj, ensure_ascii=False))
            target_id = f"{SETTINGS_KEY_PENALTY_STATE_BY_ROLE}:{r}"
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_tool_wire_penalty_reset",
            target_type="app_setting",
            target_id=target_id,
            status="ok",
            detail={"reset": True, "role": r},
        )
        return {"ok": True, "penalty_state": {}, "role": r}

    @router.post("/admin/api/mcp/tool-wire/policies")
    def api_mcp_tool_wire_policies_save(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        from oclaw.platform.llm.tool_wire_policy import (
            SETTINGS_KEY_TOOL_POLICIES,
            SETTINGS_KEY_TOOL_POLICIES_BY_ROLE,
            load_tool_policies_dict_for_role,
        )

        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        role = str(payload.get("role") or "").strip().lower()
        pol_in = payload.get("policies")
        if not isinstance(pol_in, dict):
            raise HTTPException(status_code=400, detail="policies must be an object")
        merged = dict(load_tool_policies_dict_for_role(store, role=role or None))

        def _coerce_lv(v: Any) -> int | None:
            try:
                n = int(v)
            except (TypeError, ValueError):
                return None
            if n == 9999:
                return 9999
            if n <= 0:
                return 0
            return min(n, 9998)

        clears = payload.get("clears")
        if isinstance(clears, list):
            for w in clears:
                wn = str(w or "").strip()
                if wn.startswith("mcp__"):
                    merged.pop(wn, None)
        for k, v in pol_in.items():
            wn = str(k or "").strip()
            if not wn.startswith("mcp__"):
                continue
            co = _coerce_lv(v)
            if co is None:
                continue
            merged[wn] = co
        if not role:
            store.set_setting(SETTINGS_KEY_TOOL_POLICIES, json.dumps(merged, ensure_ascii=False))
            target_id = SETTINGS_KEY_TOOL_POLICIES
        else:
            raw = str(store.get_setting(SETTINGS_KEY_TOOL_POLICIES_BY_ROLE) or "").strip() or "{}"
            try:
                outer = json.loads(raw)
            except Exception:
                outer = {}
            if not isinstance(outer, dict):
                outer = {}
            outer[role] = merged
            store.set_setting(SETTINGS_KEY_TOOL_POLICIES_BY_ROLE, json.dumps(outer, ensure_ascii=False))
            target_id = f"{SETTINGS_KEY_TOOL_POLICIES_BY_ROLE}:{role}"
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_tool_wire_policies_update",
            target_type="app_setting",
            target_id=target_id,
            status="ok",
            detail={"count": len(merged), "role": role},
        )
        return {"ok": True, "policies": merged, "role": role}

    @router.post("/admin/api/mcp/tool-wire/policies/batch")
    def api_mcp_tool_wire_policies_batch(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        from oclaw.platform.llm.tool_wire_policy import (
            SETTINGS_KEY_TOOL_POLICIES,
            SETTINGS_KEY_TOOL_POLICIES_BY_ROLE,
            load_tool_policies_dict_for_role,
        )

        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        try:
            lv = int(payload.get("level"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="level must be int")
        if lv != 9999 and (lv < 0 or lv > 9998):
            raise HTTPException(status_code=400, detail="invalid level")
        names = payload.get("wire_names")
        if not isinstance(names, list) or not names:
            raise HTTPException(status_code=400, detail="wire_names must be non-empty array")
        role = str(payload.get("role") or "").strip().lower()
        if role:
            valid_roles = set(_ordered_mcp_roles())
            if role not in valid_roles:
                raise HTTPException(status_code=400, detail="invalid_role")
        merged = dict(load_tool_policies_dict_for_role(store, role=role or None))
        for wn in names:
            s = str(wn or "").strip()
            if not s.startswith("mcp__"):
                continue
            if lv == 9999:
                merged[s] = 9999
            elif lv <= 0:
                merged[s] = 0
            else:
                merged[s] = min(lv, 9998)
        if not role:
            store.set_setting(SETTINGS_KEY_TOOL_POLICIES, json.dumps(merged, ensure_ascii=False))
            target_id = SETTINGS_KEY_TOOL_POLICIES
        else:
            raw = str(store.get_setting(SETTINGS_KEY_TOOL_POLICIES_BY_ROLE) or "").strip() or "{}"
            try:
                outer = json.loads(raw)
            except Exception:
                outer = {}
            if not isinstance(outer, dict):
                outer = {}
            outer[role] = merged
            store.set_setting(SETTINGS_KEY_TOOL_POLICIES_BY_ROLE, json.dumps(outer, ensure_ascii=False))
            target_id = f"{SETTINGS_KEY_TOOL_POLICIES_BY_ROLE}:{role}"
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_tool_wire_policies_batch",
            target_type="app_setting",
            target_id=target_id,
            status="ok",
            detail={"level": lv, "n": len(names), "role": role},
        )
        return {"ok": True, "policies": merged, "role": role}

    @router.get("/admin/api/mcp/market/search")
    def api_mcp_market_search(
        q: str = Query(default=""),
        per_source_limit: int = Query(default=6),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        query = str(q or "").strip()
        if not query:
            return {"ok": True, "items": []}
        items = search_mcp_market(query, per_source_limit=per_source_limit)
        return {"ok": True, "items": items}

    @router.get("/admin/api/mcp/market/trending")
    def api_mcp_market_trending(
        per_source_limit: int = Query(default=5),
        refresh: int = Query(default=0),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        items = trending_mcp_market(force_refresh=bool(int(refresh or 0)), per_source_limit=per_source_limit)
        return {"ok": True, "items": items}

    @router.get("/admin/api/mcp/dependencies")
    def api_mcp_dependencies(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        return {"ok": True, "items": detect_local_dependencies()}

    @router.get("/admin/api/mcp/binding")
    def api_mcp_binding(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        available = _ordered_mcp_roles()
        servers = store.list_mcp_servers(enabled_only=False)
        normalized_servers = [
            {
                "server_id": str(x.get("server_id") or ""),
                "source_type": str(x.get("source_type") or ""),
                "enabled": bool(x.get("enabled")),
            }
            for x in servers
            if str(x.get("server_id") or "").strip()
        ]
        mapping = _normalize_mcp_specialist_binding(
            available_specialists=available,
            servers=normalized_servers,
            mapping=_load_mcp_specialist_binding(store),
        )
        return {"ok": True, "available_specialists": available, "servers": normalized_servers, "mapping": mapping}

    @router.post("/admin/api/mcp/binding")
    def api_mcp_binding_save(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        available = _ordered_mcp_roles()
        servers = store.list_mcp_servers(enabled_only=False)
        normalized_servers = [
            {
                "server_id": str(x.get("server_id") or ""),
                "source_type": str(x.get("source_type") or ""),
                "enabled": bool(x.get("enabled")),
            }
            for x in servers
            if str(x.get("server_id") or "").strip()
        ]
        mapping_raw = payload.get("mapping") if isinstance(payload.get("mapping"), dict) else {}
        mapping = _normalize_mcp_specialist_binding(
            available_specialists=available,
            servers=normalized_servers,
            mapping=mapping_raw,
        )
        store.set_setting("mcp_specialist_server_binding", json.dumps(mapping, ensure_ascii=False))
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_binding_update",
            target_type="mcp_config",
            target_id="specialist_server_binding",
            status="ok",
            detail={"mapping": mapping},
        )
        return {"ok": True, "available_specialists": available, "servers": normalized_servers, "mapping": mapping}

    @router.get("/admin/api/mcp/specialists")
    def api_mcp_specialists(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        available = _ordered_mcp_roles()
        raw = str(store.get_setting("mcp_allowed_specialists") or "").strip() or "generalist,manager"
        allowed = [x.strip().lower() for x in raw.split(",") if x.strip()]
        allowed_set = set(allowed)
        ordered = [x for x in available if x in allowed_set]
        if not ordered:
            ordered = ["generalist"] if "generalist" in available else (available[:1] if available else [])
        return {"ok": True, "available_specialists": available, "allowed_specialists": ordered}

    @router.post("/admin/api/mcp/specialists")
    def api_mcp_specialists_save(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        available = _ordered_mcp_roles()
        available_set = set(available)
        raw = payload.get("allowed_specialists")
        items = raw if isinstance(raw, list) else []
        allowset = {str(x).strip().lower() for x in items if str(x).strip().lower() in available_set}
        if not allowset:
            defaults = {x for x in ("generalist", "manager") if x in available_set}
            allowset = defaults if defaults else (set(available[:1]) if available else set())
        ordered = [x for x in available if x in allowset]
        store.set_setting("mcp_allowed_specialists", ",".join(ordered))
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_specialists_update",
            target_type="mcp_config",
            target_id="allowed_specialists",
            status="ok",
            detail={"allowed_specialists": ordered},
        )
        return {"ok": True, "available_specialists": available, "allowed_specialists": ordered}

    @router.get("/admin/api/experts")
    def api_experts_list(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        items = [_serialize_expert_row(x) for x in list_experts()]
        return {"ok": True, "items": items}

    @router.post("/admin/api/experts")
    def api_experts_create(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        expert_id = normalize_expert_id(payload.get("id"))
        display_name_en = str(payload.get("display_name_en") or "").strip()
        display_name_zh = str(payload.get("display_name_zh") or "").strip()
        role = str(payload.get("role") or "").strip().lower()
        files_raw = payload.get("files") if isinstance(payload.get("files"), dict) else {}
        try:
            files = _sanitize_expert_files_payload(files_raw)
            created = create_expert(
                expert_id=expert_id,
                files=files,
                display_name_en=display_name_en,
                display_name_zh=display_name_zh,
                role=role or None,
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="expert_create",
            target_type="expert",
            target_id=str(created.get("id") or ""),
            status="ok",
            detail={"id": str(created.get("id") or "")},
        )
        items = [_serialize_expert_row(x) for x in list_experts()]
        return {"ok": True, "created": str(created.get("id") or ""), "items": items}

    @router.patch("/admin/api/experts/{expert_id}")
    def api_experts_update(
        expert_id: str,
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        files_raw = payload.get("files") if isinstance(payload.get("files"), dict) else {}
        eid = normalize_expert_id(expert_id)
        display_name_en = str(payload.get("display_name_en") or "").strip()
        display_name_zh = str(payload.get("display_name_zh") or "").strip()
        role = str(payload.get("role") or "").strip().lower()
        try:
            files = _sanitize_expert_files_payload(files_raw)
            update_expert_files(expert_id=eid, files=files)
            update_expert_meta(
                expert_id=eid,
                display_name_en=display_name_en,
                display_name_zh=display_name_zh,
                role=role or None,
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="expert_update",
            target_type="expert",
            target_id=eid,
            status="ok",
            detail={"id": eid, "updated_files": sorted(list(files.keys()))[:10]},
        )
        items = [_serialize_expert_row(x) for x in list_experts()]
        return {"ok": True, "updated": eid, "items": items}

    @router.delete("/admin/api/experts/{expert_id}")
    def api_experts_delete(expert_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        eid = normalize_expert_id(expert_id)
        try:
            delete_expert(eid)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="expert_delete",
            target_type="expert",
            target_id=eid,
            status="ok",
            detail={"id": eid},
        )
        items = [_serialize_expert_row(x) for x in list_experts()]
        return {"ok": True, "deleted": eid, "items": items}

    @router.post("/admin/api/mcp/install")
    def api_mcp_install(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        source_type = str(payload.get("source_type") or "").strip().lower()
        source_ref = str(payload.get("source_ref") or "").strip()
        if source_type not in {"github", "npm", "pypi"} or not source_ref:
            return {"ok": False, "error": "invalid_source"}
        server_id = _safe_server_id(str(payload.get("server_id") or source_ref))
        manifest = McpServerManifest(
            server_id=server_id,
            source_type=source_type,
            source_ref=source_ref,
            version=str(payload.get("version") or "").strip(),
            entry_command=str(payload.get("entry_command") or "").strip(),
            entry_args=_expand_mcp_entry_args(payload.get("entry_args") if isinstance(payload.get("entry_args"), list) else []),
            env_schema=payload.get("env_schema") if isinstance(payload.get("env_schema"), dict) else {},
            permissions=[str(x) for x in (payload.get("required_permissions") or [])],
            risk_level=str(payload.get("risk_level") or "high"),
            enabled=bool(payload.get("enabled", True)),
            timeout_s=float(payload.get("timeout_s") or 30.0),
        )
        dry_run = bool(payload.get("dry_run", False))
        install = install_mcp_server(manifest, dry_run=dry_run)
        store.upsert_mcp_server(
            server_id=manifest.server_id,
            source_type=manifest.source_type,
            source_ref=manifest.source_ref,
            version=manifest.version,
            entry_command=manifest.entry_command,
            entry_args=manifest.entry_args,
            env_schema=manifest.env_schema,
            required_permissions=manifest.permissions,
            risk_level=manifest.risk_level,
            timeout_s=manifest.timeout_s,
            enabled=manifest.enabled if install.ok else False,
        )
        store.add_mcp_installation_log(
            server_id=manifest.server_id,
            status="ok" if install.ok else "error",
            error_code=install.error_code,
            detail={"error": install.error, **(install.details or {})},
            install_command=install.install_command,
        )
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_install",
            target_type="mcp_server",
            target_id=manifest.server_id,
            status="ok" if install.ok else "error",
            detail={"source_type": source_type, "source_ref": source_ref, "error_code": install.error_code},
        )
        if not install.ok:
            return {"ok": False, "server_id": manifest.server_id, "error_code": install.error_code, "error": install.error}
        persist_mcp_migrated_file(store)
        return {
            "ok": True,
            "server_id": manifest.server_id,
            "install_command": install.install_command,
            "mcp_migrated_saved": str(mcp_migrated_json_path()),
        }

    @router.post("/admin/api/mcp/reinstall")
    def api_mcp_reinstall(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        server_id = str(payload.get("server_id") or "").strip()
        if not server_id:
            return {"ok": False, "error": "server_id_required"}
        rows = store.list_mcp_servers(enabled_only=False)
        row = next((x for x in rows if str(x.get("server_id") or "") == server_id), None)
        if not row:
            return {"ok": False, "error": "server_not_found"}
        manifest = McpServerManifest(
            server_id=str(row.get("server_id") or ""),
            source_type=str(row.get("source_type") or ""),
            source_ref=str(row.get("source_ref") or ""),
            version=str(row.get("version") or ""),
            entry_command=str(row.get("entry_command") or ""),
            entry_args=[str(x) for x in (row.get("entry_args") or []) if str(x).strip()],
            env_schema=row.get("env_schema") if isinstance(row.get("env_schema"), dict) else {},
            permissions=[str(x) for x in (row.get("required_permissions") or [])],
            risk_level=str(row.get("risk_level") or "high"),
            enabled=bool(row.get("enabled")),
            timeout_s=float(row.get("timeout_s") or 30.0),
        )
        dry_run = bool(payload.get("dry_run", False))
        install = install_mcp_server(manifest, dry_run=dry_run)
        store.upsert_mcp_server(
            server_id=manifest.server_id,
            source_type=manifest.source_type,
            source_ref=manifest.source_ref,
            version=manifest.version,
            entry_command=manifest.entry_command,
            entry_args=manifest.entry_args,
            env_schema=manifest.env_schema,
            required_permissions=manifest.permissions,
            risk_level=manifest.risk_level,
            timeout_s=manifest.timeout_s,
            enabled=manifest.enabled if install.ok else False,
        )
        store.add_mcp_installation_log(
            server_id=manifest.server_id,
            status="ok" if install.ok else "error",
            error_code=install.error_code,
            detail={"error": install.error, **(install.details or {}), "reinstall": True},
            install_command=install.install_command,
        )
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_reinstall",
            target_type="mcp_server",
            target_id=manifest.server_id,
            status="ok" if install.ok else "error",
            detail={"error_code": install.error_code},
        )
        if not install.ok:
            return {"ok": False, "server_id": manifest.server_id, "error_code": install.error_code, "error": install.error}
        persist_mcp_migrated_file(store)
        return {
            "ok": True,
            "server_id": manifest.server_id,
            "install_command": install.install_command,
            "mcp_migrated_saved": str(mcp_migrated_json_path()),
        }

    @router.post("/admin/api/mcp/update")
    def api_mcp_update(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        server_id = str(payload.get("server_id") or "").strip()
        enabled_only = bool(payload.get("enabled_only", True))
        dry_run = bool(payload.get("dry_run", False))
        sync_tools = bool(payload.get("sync_tools", True))
        version_override = str(payload.get("version") or "").strip()
        update_to_latest = bool(payload.get("update_to_latest", True))

        rows = store.list_mcp_servers(enabled_only=enabled_only if not server_id else False)
        if server_id:
            rows = [x for x in rows if str(x.get("server_id") or "").strip() == server_id]
        if not rows:
            return {"ok": False, "error": "server_not_found"}

        apply_gateway_mcp_env_to_os()
        out: list[dict[str, Any]] = []
        for row in rows:
            sid = str(row.get("server_id") or "").strip()
            req_version = version_override
            if not req_version:
                req_version = "" if update_to_latest else str(row.get("version") or "").strip()
            manifest = McpServerManifest(
                server_id=sid,
                source_type=str(row.get("source_type") or ""),
                source_ref=str(row.get("source_ref") or ""),
                version=req_version,
                entry_command=str(row.get("entry_command") or ""),
                entry_args=[str(x) for x in (row.get("entry_args") or []) if str(x).strip()],
                env_schema=row.get("env_schema") if isinstance(row.get("env_schema"), dict) else {},
                permissions=[str(x) for x in (row.get("required_permissions") or [])],
                risk_level=str(row.get("risk_level") or "high"),
                enabled=bool(row.get("enabled")),
                timeout_s=float(row.get("timeout_s") or 30.0),
            )
            install = install_mcp_server(manifest, dry_run=dry_run)
            store.upsert_mcp_server(
                server_id=manifest.server_id,
                source_type=manifest.source_type,
                source_ref=manifest.source_ref,
                version=manifest.version,
                entry_command=manifest.entry_command,
                entry_args=manifest.entry_args,
                env_schema=manifest.env_schema,
                required_permissions=manifest.permissions,
                risk_level=manifest.risk_level,
                timeout_s=manifest.timeout_s,
                enabled=manifest.enabled if install.ok else False,
            )
            item: dict[str, Any] = {
                "server_id": manifest.server_id,
                "ok": bool(install.ok),
                "error_code": str(install.error_code or ""),
                "error": str(install.error or ""),
                "install_command": str(install.install_command or ""),
                "requested_version": req_version,
                "tools_synced": 0,
            }
            if install.ok and sync_tools and (not dry_run):
                latest_row = next(
                    (x for x in store.list_mcp_servers(enabled_only=False) if str(x.get("server_id") or "") == sid),
                    None,
                )
                if isinstance(latest_row, dict):
                    hs = _mcp_health_and_sync_one(store, latest_row)
                    if isinstance(hs, dict):
                        item["tools_synced"] = int(hs.get("tools_synced") or 0)
                        if not bool(hs.get("ok")):
                            item["ok"] = False
                            item["error_code"] = str(hs.get("error_code") or "mcp_sync_failed")
                            item["error"] = str(hs.get("error") or "sync_failed")
            store.add_mcp_installation_log(
                server_id=manifest.server_id,
                status="ok" if item["ok"] else "error",
                error_code=str(item["error_code"] or None),
                detail={
                    "error": item["error"],
                    "update": True,
                    "requested_version": req_version,
                    "tools_synced": int(item.get("tools_synced") or 0),
                },
                install_command=install.install_command,
            )
            out.append(item)

        ok_count = len([x for x in out if bool(x.get("ok"))])
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_update" if server_id else "mcp_update_batch",
            target_type="mcp_server",
            target_id=server_id or "batch",
            status="ok" if ok_count == len(out) else "error",
            detail={
                "enabled_only": enabled_only,
                "dry_run": dry_run,
                "sync_tools": sync_tools,
                "update_to_latest": update_to_latest,
                "requested_version": version_override,
                "ok_count": ok_count,
                "error_count": len(out) - ok_count,
            },
        )
        if ok_count > 0:
            persist_mcp_migrated_file(store)
        return {
            "ok": ok_count == len(out),
            "total": len(out),
            "ok_count": ok_count,
            "error_count": len(out) - ok_count,
            "items": out,
            "mcp_migrated_saved": str(mcp_migrated_json_path()),
        }

    @router.post("/admin/api/mcp/uninstall")
    def api_mcp_uninstall(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        server_id = str(payload.get("server_id") or "").strip()
        remove_record = bool(payload.get("remove_record", True))
        if not server_id:
            return {"ok": False, "error": "server_id_required"}
        rows = store.list_mcp_servers(enabled_only=False)
        row = next((x for x in rows if str(x.get("server_id") or "") == server_id), None)
        if not row:
            return {"ok": False, "error": "server_not_found"}
        manifest = McpServerManifest(
            server_id=str(row.get("server_id") or ""),
            source_type=str(row.get("source_type") or ""),
            source_ref=str(row.get("source_ref") or ""),
            version=str(row.get("version") or ""),
            entry_command=str(row.get("entry_command") or ""),
            entry_args=[str(x) for x in (row.get("entry_args") or []) if str(x).strip()],
            env_schema=row.get("env_schema") if isinstance(row.get("env_schema"), dict) else {},
            permissions=[str(x) for x in (row.get("required_permissions") or [])],
            risk_level=str(row.get("risk_level") or "high"),
            enabled=False,
            timeout_s=float(row.get("timeout_s") or 30.0),
        )
        dry_run = bool(payload.get("dry_run", False))
        res = uninstall_mcp_server(manifest, dry_run=dry_run)
        store.add_mcp_installation_log(
            server_id=manifest.server_id,
            status="ok" if res.ok else "error",
            error_code=res.error_code,
            detail={"error": res.error, **(res.details or {}), "uninstall": True},
            install_command=res.install_command,
        )
        deleted = {"registry": 0, "tools": 0, "health": 0, "install_logs": 0}
        if res.ok and remove_record and not dry_run:
            deleted = store.delete_mcp_server(server_id=manifest.server_id)
            mapping = _load_mcp_specialist_binding(store)
            for sp, sids in list(mapping.items()):
                mapping[sp] = [sid for sid in sids if sid != manifest.server_id]
            store.set_setting("mcp_specialist_server_binding", json.dumps(mapping, ensure_ascii=False))
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_uninstall",
            target_type="mcp_server",
            target_id=manifest.server_id,
            status="ok" if res.ok else "error",
            detail={"error_code": res.error_code, "remove_record": remove_record, "deleted": deleted},
        )
        if not res.ok:
            return {"ok": False, "server_id": manifest.server_id, "error_code": res.error_code, "error": res.error}
        persist_mcp_migrated_file(store)
        return {"ok": True, "server_id": manifest.server_id, "uninstall_command": res.install_command, "deleted": deleted}

    @router.post("/admin/api/mcp/delete")
    def api_mcp_delete(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        server_id = str(payload.get("server_id") or "").strip()
        if not server_id:
            return {"ok": False, "error": "server_id_required"}
        deleted = store.delete_mcp_server(server_id=server_id)
        mapping = _load_mcp_specialist_binding(store)
        for sp, sids in list(mapping.items()):
            mapping[sp] = [sid for sid in sids if sid != server_id]
        store.set_setting("mcp_specialist_server_binding", json.dumps(mapping, ensure_ascii=False))
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_delete",
            target_type="mcp_server",
            target_id=server_id,
            status="ok" if any(int(v or 0) > 0 for v in deleted.values()) else "miss",
            detail={"deleted": deleted},
        )
        if any(int(v or 0) > 0 for v in deleted.values()):
            persist_mcp_migrated_file(store)
        return {"ok": True, "server_id": server_id, "deleted": deleted}

    @router.post("/admin/api/mcp/preflight")
    def api_mcp_preflight(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        source_type = str(payload.get("source_type") or "").strip().lower()
        source_ref = str(payload.get("source_ref") or "").strip()
        if source_type not in {"github", "npm", "pypi"} or not source_ref:
            return {"ok": False, "error_code": "mcp_invalid_source", "error": "invalid_source"}
        manifest = McpServerManifest(
            server_id=_safe_server_id(str(payload.get("server_id") or source_ref)),
            source_type=source_type,
            source_ref=source_ref,
            version=str(payload.get("version") or "").strip(),
            entry_command=str(payload.get("entry_command") or "").strip(),
            entry_args=_expand_mcp_entry_args(payload.get("entry_args") if isinstance(payload.get("entry_args"), list) else []),
            env_schema=payload.get("env_schema") if isinstance(payload.get("env_schema"), dict) else {},
            permissions=[str(x) for x in (payload.get("required_permissions") or [])],
            risk_level=str(payload.get("risk_level") or "high"),
            enabled=bool(payload.get("enabled", True)),
            timeout_s=float(payload.get("timeout_s") or 30.0),
        )
        res = preflight_mcp_server(manifest)
        return {"ok": bool(res.get("ok")), **res}

    @router.post("/admin/api/mcp/toggle")
    def api_mcp_toggle(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        server_id = str(payload.get("server_id") or "").strip()
        enabled = bool(payload.get("enabled"))
        if not server_id:
            return {"ok": False, "error": "server_id_required"}
        n = store.set_mcp_server_enabled(server_id=server_id, enabled=enabled)
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_toggle",
            target_type="mcp_server",
            target_id=server_id,
            status="ok" if n > 0 else "miss",
            detail={"enabled": enabled},
        )
        return {"ok": True, "updated": n}

    @router.post("/admin/api/mcp/healthcheck")
    def api_mcp_healthcheck(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        apply_gateway_mcp_env_to_os()
        server_id = str(payload.get("server_id") or "").strip()
        if not server_id:
            return {"ok": False, "error": "server_id_required"}
        rows = store.list_mcp_servers(enabled_only=False)
        row = next((x for x in rows if str(x.get("server_id") or "") == server_id), None)
        if not row:
            return {"ok": False, "error": "server_not_found"}
        cmd = str(row.get("entry_command") or "").strip()
        args = [str(x) for x in (row.get("entry_args") or []) if str(x).strip()]
        if not cmd:
            return {"ok": False, "error_code": "mcp_entry_missing", "error": "entry_command_missing"}
        if _is_bailian_webparser_remote(entry_command=cmd, entry_args=args):
            detail = {"ok": True, "status": "ok", "compat_mode": "bailian_webparser", "tools_count": 1}
            store.set_mcp_server_health(server_id=server_id, status="ok", detail=detail)
            return {"ok": True, "response": detail}
        rt = McpProcessRuntime(
            build_mcp_process_command(cmd, args, store=store),
            timeout_s=float(row.get("timeout_s") or 30.0),
        )
        try:
            response = rt.health()
            ok = bool(response.get("ok"))
            store.set_mcp_server_health(server_id=server_id, status="ok" if ok else "error", detail=response)
            if ok:
                return {"ok": True, "response": response}
            return {
                "ok": False,
                "error_code": str(response.get("error_code") or "mcp_healthcheck_failed"),
                "error": str(response.get("error") or "healthcheck_failed"),
                "response": response,
            }
        except Exception as exc:
            store.set_mcp_server_health(
                server_id=server_id,
                status="error",
                detail={"error_code": "mcp_healthcheck_failed", "error": f"{type(exc).__name__}: {exc}"},
            )
            return {"ok": False, "error_code": "mcp_healthcheck_failed", "error": f"{type(exc).__name__}: {exc}"}
        finally:
            rt.stop()

    @router.post("/admin/api/mcp/tools/sync")
    def api_mcp_tools_sync(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        apply_gateway_mcp_env_to_os()
        server_id = str(payload.get("server_id") or "").strip()
        if not server_id:
            return {"ok": False, "error": "server_id_required"}
        rows = store.list_mcp_servers(enabled_only=False)
        row = next((x for x in rows if str(x.get("server_id") or "") == server_id), None)
        if not row:
            return {"ok": False, "error": "server_not_found"}
        cmd = str(row.get("entry_command") or "").strip()
        args = [str(x) for x in (row.get("entry_args") or []) if str(x).strip()]
        if not cmd:
            return {"ok": False, "error_code": "mcp_entry_missing", "error": "entry_command_missing"}
        if _is_bailian_webparser_remote(entry_command=cmd, entry_args=args):
            norm = _bailian_webparser_virtual_tools()
            store.replace_mcp_server_tools(server_id=server_id, tools=norm)
            store.set_mcp_server_health(
                server_id=server_id,
                status="ok",
                detail={"synced_tools": len(norm), "compat_mode": "bailian_webparser"},
            )
            return {"ok": True, "server_id": server_id, "tools": norm, "compat_mode": "bailian_webparser"}
        rt = McpProcessRuntime(
            build_mcp_process_command(cmd, args, store=store),
            timeout_s=float(row.get("timeout_s") or 30.0),
        )
        try:
            response = rt.tools_list()
            items = response.get("tools") if isinstance(response, dict) else None
            if not isinstance(items, list):
                return {"ok": False, "error_code": "mcp_tools_list_invalid", "error": "tools_list_invalid"}
            norm = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                tool_name = str(it.get("tool_name") or it.get("name") or "").strip()
                if not tool_name:
                    continue
                norm.append(
                    {
                        "tool_name": tool_name,
                        "description": str(it.get("description") or ""),
                        "parameters": it.get("parameters") if isinstance(it.get("parameters"), dict) else {},
                    }
                )
            store.replace_mcp_server_tools(server_id=server_id, tools=norm)
            store.set_mcp_server_health(server_id=server_id, status="ok", detail={"synced_tools": len(norm)})
            return {"ok": True, "server_id": server_id, "tools": norm}
        finally:
            rt.stop()

    @router.post("/admin/api/mcp/check-all")
    def api_mcp_check_all(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        apply_gateway_mcp_env_to_os()
        enabled_only = bool(payload.get("enabled_only", True))
        rows = store.list_mcp_servers(enabled_only=enabled_only)
        out: list[dict[str, Any]] = []
        for row in rows:
            item = _mcp_health_and_sync_one(store, row)
            if item is not None:
                out.append(item)
        ok_count = len([x for x in out if bool(x.get("ok"))])
        return {"ok": True, "total": len(out), "ok_count": ok_count, "error_count": len(out) - ok_count, "items": out}

    @router.post("/admin/api/mcp/check-updates")
    def api_mcp_check_updates(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        enabled_only = bool(payload.get("enabled_only", True))
        rows = store.list_mcp_servers(enabled_only=enabled_only)
        items = [_check_mcp_update_row(row) for row in rows]
        update_count = len([x for x in items if bool(x.get("has_update"))])
        return {
            "ok": True,
            "total": len(items),
            "update_count": update_count,
            "up_to_date_count": len(items) - update_count,
            "items": items,
        }

    @router.post("/admin/api/mcp/repair-weak")
    def api_mcp_repair_weak(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """
        For enabled MCP rows whose persisted health is not ``ok`` and/or cached tool list is empty,
        run the same health + tools/list + replace flow as ``check-all`` (only those servers).
        """
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        apply_gateway_mcp_env_to_os()
        enabled_only = bool(payload.get("enabled_only", True))
        rows = store.list_mcp_servers(enabled_only=enabled_only)
        health_by_sid = {str(x.get("server_id") or ""): x for x in store.list_mcp_server_health()}
        targets: list[dict[str, Any]] = []
        skipped_healthy = 0
        for row in rows:
            sid = str(row.get("server_id") or "").strip()
            if not sid:
                continue
            h = health_by_sid.get(sid) or {}
            st = str(h.get("status") or "").strip().lower()
            n_tools = len(store.list_mcp_server_tools(server_id=sid))
            if st == "ok" and n_tools > 0:
                skipped_healthy += 1
                continue
            targets.append(row)
        out: list[dict[str, Any]] = []
        for row in targets:
            item = _mcp_health_and_sync_one(store, row)
            if item is not None:
                out.append(item)
        ok_count = len([x for x in out if bool(x.get("ok"))])
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="mcp_repair_weak",
            target_type="mcp_server",
            target_id="batch",
            status="ok",
            detail={
                "selected": len(targets),
                "skipped_healthy": skipped_healthy,
                "ok_count": ok_count,
                "error_count": len(out) - ok_count,
            },
        )
        return {
            "ok": True,
            "selected": len(targets),
            "skipped_healthy": skipped_healthy,
            "total": len(out),
            "ok_count": ok_count,
            "error_count": len(out) - ok_count,
            "items": out,
        }

    @router.post("/admin/api/mcp/e2e-check")
    def api_mcp_e2e_check(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        apply_gateway_mcp_env_to_os()
        sess = store.create_session("mcp-e2e-check")
        session_id = str(sess.id)
        try:
            store.add_message(session_id=session_id, role="user", content="mcp e2e check")
            reg = default_registry(expert="generalist+workspace+productivity", specialist="generalist")
            runtime = ToolExecutor()
            names = {t.name for t in reg.list()}
            plans, skipped_servers = build_mcp_e2e_probe_plans(reg, workspace_root=str(PROJECT_ROOT.resolve()))
            out: list[dict[str, Any]] = []
            for server_id, full_name, args in plans:
                row = {
                    "server_id": server_id,
                    "tool_name": full_name,
                    "in_registry": full_name in names,
                    "ok": False,
                    "duration_ms": 0,
                    "error": "",
                }
                if not bool(row["in_registry"]):
                    row["error"] = "tool_not_in_registry"
                    out.append(row)
                    continue
                call = LLMToolCall(id=f"call_{server_id}", name=full_name, arguments=args)
                tool_ctx = ToolExecutionContext(
                    store=store,
                    tools=reg,
                    session_id=session_id,
                    lang="zh",
                    user_text=f"e2e check {full_name}",
                    specialist="generalist",
                    task_kind="mcp_e2e",
                    policy_engine=None,
                    trace_id="mcp-e2e",
                    parent_span_id="root",
                )
                _tool_msgs, result_by_id = runtime.execute_tool_uses(
                    ctx=tool_ctx,
                    assistant_msg_id=0,
                    tool_uses=[call],
                    on_tool_ui=None,
                    should_stop=None,
                )
                hit = result_by_id.get(call.id)
                if hit:
                    result, dur = hit
                    row["duration_ms"] = int(dur or 0)
                    row["ok"] = bool((result or {}).get("ok"))
                    row["error"] = str((result or {}).get("error") or (result or {}).get("error_code") or "")
                else:
                    row["error"] = "no_result"
                out.append(row)
            for sid in skipped_servers:
                out.append(
                    {
                        "server_id": sid,
                        "tool_name": "",
                        "in_registry": True,
                        "ok": False,
                        "duration_ms": 0,
                        "error": "e2e_no_probe_candidate",
                    }
                )
            ok_count = len([x for x in out if bool(x.get("ok"))])
            store.add_admin_audit_log(
                actor_tenant_id=ctx["tenant_id"],
                actor_user_id=ctx["user_id"],
                action="mcp_e2e_check",
                target_type="mcp_server",
                target_id="all",
                status="ok",
                detail={"session_id": session_id, "total": len(out), "ok_count": ok_count},
            )
            return {
                "ok": True,
                "session_id": session_id,
                "total": len(out),
                "ok_count": ok_count,
                "error_count": len(out) - ok_count,
                "items": out,
            }
        except Exception as e:
            return {"ok": False, "session_id": session_id, "error": f"{type(e).__name__}: {e}"}

    @router.get("/admin/api/memory/hits")
    def api_memory_hits(
        tenant_id: str | None = Query(default=None),
        user_id: str | None = Query(default=None),
        limit: int = Query(default=100),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        if tenant_id:
            _require_tenant_scope(ctx, tenant_id)
        rows = store.list_memory_hit_logs(tenant_id=tenant_id, user_id=user_id, limit=limit)
        return {"ok": True, "hits": rows}

    @router.get("/admin/api/memory/stats")
    def api_memory_stats(
        tenant_id: str | None = Query(default=None),
        user_id: str | None = Query(default=None),
        limit: int = Query(default=300),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        if tenant_id:
            _require_tenant_scope(ctx, tenant_id)
        hits = store.list_memory_hit_logs(tenant_id=tenant_id, user_id=user_id, limit=limit)
        items = store.list_memory_items(tenant_id=tenant_id, user_id=user_id, limit=500, offset=0)
        hit_count = len(hits)
        avg_score = (sum(float(x.get("score") or 0.0) for x in hits) / hit_count) if hit_count else 0.0
        source_count: dict[str, int] = {}
        for h in hits:
            src = str(h.get("source") or "unknown")
            source_count[src] = source_count.get(src, 0) + 1
        top_sources = sorted(source_count.items(), key=lambda x: x[1], reverse=True)[:5]
        return {
            "ok": True,
            "stats": {
                "hit_count": hit_count,
                "avg_score": avg_score,
                "item_count": len(items),
                "top_sources": [{"source": k, "count": v} for k, v in top_sources],
            },
        }

    @router.get("/admin/api/memory/items")
    def api_memory_items(
        tenant_id: str | None = Query(default=None),
        user_id: str | None = Query(default=None),
        limit: int = Query(default=100),
        offset: int = Query(default=0),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        if tenant_id:
            _require_tenant_scope(ctx, tenant_id)
        rows = store.list_memory_items(tenant_id=tenant_id, user_id=user_id, limit=limit, offset=offset)
        runtime = read_vector_memory_runtime(store)
        return {"ok": True, "items": rows, "runtime": runtime.__dict__}

    @router.post("/admin/api/memory/delete")
    def api_memory_delete(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:memory:write")
        memory_id = str(payload.get("memory_id") or "").strip()
        if not memory_id:
            return {"ok": False, "error": "memory_id is required"}
        deleted = store.delete_memory_item(memory_id=memory_id)
        return {"ok": True, "deleted": deleted}

    @router.post("/admin/api/memory/reindex")
    def api_memory_reindex(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:memory:write")
        tenant_id = str(payload.get("tenant_id") or "").strip() or None
        if tenant_id:
            _require_tenant_scope(ctx, tenant_id)
        user_id = str(payload.get("user_id") or "").strip() or None
        from oclaw.platform.embeddings.embedding_client import build_default_embedding_client
        from oclaw.runtime.orchestration.vector_store import build_vector_store, MemoryVectorItem

        client = build_default_embedding_client()
        vector = build_vector_store(store)
        items = store.list_memory_items(tenant_id=tenant_id, user_id=user_id, limit=500, offset=0)
        updated = 0
        for row in items:
            content = str(row.get("content") or "").strip()
            if not content:
                continue
            emb = client.embed(content)
            item = MemoryVectorItem(
                memory_id=str(row.get("memory_id") or ""),
                tenant_id=str(row.get("tenant_id") or ""),
                user_id=str(row.get("user_id") or ""),
                session_id=str(row.get("session_id") or ""),
                memory_type=str(row.get("memory_type") or "semantic_memory"),
                content=content,
                confidence=float(row.get("confidence") or 0.0),
                created_at=str(row.get("created_at") or ""),
                updated_at=str(row.get("updated_at") or ""),
                expires_at=str(row.get("expires_at") or "") or None,
                metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
            )
            vector.upsert(item, emb.vector, model=emb.model)
            updated += 1
        return {"ok": True, "reindexed": updated}

    @router.get("/admin/api/memory/config")
    def api_memory_config(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        runtime = read_vector_memory_runtime(store)
        rag_mode = str(store.get_setting("rag_mode") or store.get_setting("AIA_RAG_MODE") or "keyword").strip().lower()
        if rag_mode not in {"keyword", "vector"}:
            rag_mode = "keyword"
        emb_mode = str(store.get_setting("AIA_RAG_EMBEDDING_MODE") or "").strip().lower()
        if emb_mode not in {"", "openai", "hash", "offline"}:
            emb_mode = ""
        ttl_raw = str(
            store.get_setting("AIA_MEMORY_EPISODIC_TTL_DAYS")
            or store.get_setting("MEMORY_EPISODIC_TTL_DAYS")
            or "90"
        ).strip()
        try:
            ttl_days = max(1, min(int(float(ttl_raw)), 3650))
        except Exception:
            ttl_days = 90
        cfg = dict(runtime.__dict__)
        cfg["rag_mode"] = rag_mode
        cfg["rag_embedding_mode"] = emb_mode
        cfg["memory_episodic_ttl_days"] = ttl_days
        return {"ok": True, "config": cfg}

    @router.post("/admin/api/memory/config")
    def api_memory_config_save(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:memory:write")
        store.set_setting("MEMORY_VECTOR_ENABLED", "1" if str(payload.get("enabled") or "").lower() in ("1", "true", "yes", "on") else "0")
        backend = str(payload.get("backend") or "sqlite").strip().lower()
        if backend not in {"sqlite", "chroma", "qdrant"}:
            backend = "sqlite"
        store.set_setting("MEMORY_VECTOR_BACKEND", backend)
        store.set_setting("MEMORY_VECTOR_TOPK", str(payload.get("top_k") or 5))
        store.set_setting(
            "MEMORY_WRITE_ENABLED",
            "1" if str(payload.get("writer_enabled") or "").lower() in ("1", "true", "yes", "on") else "0",
        )
        store.set_setting("MEMORY_WRITE_MIN_CONFIDENCE", str(payload.get("write_min_confidence") or 0.75))
        rag_mode = str(payload.get("rag_mode") or "keyword").strip().lower()
        if rag_mode not in {"keyword", "vector"}:
            rag_mode = "keyword"
        emb_mode = str(payload.get("rag_embedding_mode") or "").strip().lower()
        if emb_mode not in {"", "openai", "hash", "offline"}:
            emb_mode = ""
        ttl_in = payload.get("memory_episodic_ttl_days", 90)
        try:
            ttl_days = max(1, min(int(float(ttl_in)), 3650))
        except Exception:
            ttl_days = 90
        store.set_setting("rag_mode", rag_mode)
        store.set_setting("AIA_RAG_MODE", rag_mode)
        store.set_setting("AIA_RAG_EMBEDDING_MODE", emb_mode)
        store.set_setting("AIA_MEMORY_EPISODIC_TTL_DAYS", str(ttl_days))
        store.set_setting("MEMORY_EPISODIC_TTL_DAYS", str(ttl_days))
        return api_memory_config()

    @router.post("/admin/api/memory/cleanup-low-confidence")
    def api_memory_cleanup_low_conf(
        payload: dict[str, Any] | None = Body(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:memory:write")
        try:
            threshold = float(payload.get("max_confidence") or 0.35)
        except Exception:
            threshold = 0.35
        deleted = store.clear_low_confidence_memory(max_confidence=threshold)
        return {"ok": True, "deleted": deleted, "max_confidence": threshold}

    @router.post("/admin/api/secrets/migrate")
    def api_secrets_migrate(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        """Migrate legacy b64 secrets to fernet (requires AIA_ASSISTANT_MASTER_KEY)."""
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:tenant:write")
        try:
            res = store.migrate_secrets_to_fernet()
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
        store.add_admin_audit_log(
            actor_tenant_id=ctx["tenant_id"],
            actor_user_id=ctx["user_id"],
            action="secrets_migrate_to_fernet",
            target_type="secrets",
            target_id="all",
            status="ok",
            detail=res,
        )
        return {"ok": True, **res}

    @router.get("/admin/api/secrets/status")
    def api_secrets_status(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        """Expose legacy secret stats for admin UI warnings."""
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:read")
        stats = store.legacy_secret_stats()
        import os

        has_master_key = bool((os.getenv("AIA_ASSISTANT_MASTER_KEY") or "").strip())
        return {"ok": True, "has_master_key": has_master_key, **stats}

    @router.post("/admin/api/auth/bootstrap")
    def api_auth_bootstrap() -> dict[str, Any]:
        store = SqliteStore(db_path())
        _ensure_admin_bootstrap(store)
        return {"ok": True}

    @router.post("/admin/api/auth/login")
    def api_auth_login(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
        payload = payload or {}
        store = SqliteStore(db_path())
        _ensure_admin_bootstrap(store)
        tenant_id = str(payload.get("tenant_id") or "").strip()
        if not tenant_id:
            tenants = store.list_tenants(limit=1)
            if tenants:
                tenant_id = str((tenants[0] or {}).get("id") or "").strip()
        purpose = str(payload.get("purpose") or "console").strip().lower()
        if purpose not in {"console", "chat"}:
            purpose = "console"
        if purpose == "console":
            username = str(payload.get("username") or "administrator").strip().lower()
        else:
            username = str(payload.get("username") or "").strip().lower()
        password = str(payload.get("password") or "").strip()
        if not tenant_id or not password:
            return {"ok": False, "error": "tenant_id, username, password are required"}
        if not username:
            return {"ok": False, "error": "tenant_id, username, password are required"}
        user = store.get_user_by_username(tenant_id=tenant_id, username=username)
        if not user:
            return {"ok": False, "error": "invalid_credentials"}
        if not bool(user.get("is_active")):
            return {"ok": False, "error": "user_disabled"}
        expected = str(user.get("password_hash") or "")
        if not expected or not hmac.compare_digest(expected, _sha256_hex(password)):
            return {"ok": False, "error": "invalid_credentials"}
        role = str(user.get("role") or "member")
        if purpose == "console":
            if role == "owner" and username == "administrator":
                uid = str(user.get("id") or "")
                if uid and store.update_user_account(tenant_id=tenant_id, user_id=uid, role="admin"):
                    user = store.get_user_by_username(tenant_id=tenant_id, username=username) or user
                    role = str(user.get("role") or "member")
        perms = store.list_user_permissions(
            tenant_id=tenant_id,
            user_id=str(user.get("id") or ""),
            role=role,
        )
        token = secrets.token_urlsafe(32)
        expires = (_now_utc() + timedelta(hours=12)).isoformat()
        store.create_auth_session(
            session_token_hash=_sha256_hex(token),
            tenant_id=tenant_id,
            user_id=str(user.get("id") or ""),
            role=role,
            expires_at=expires,
        )
        return {
            "ok": True,
            "token": token,
            "session": {
                "tenant_id": tenant_id,
                "user_id": str(user.get("id") or ""),
                "username": str(user.get("username") or ""),
                "display_name": str(user.get("display_name") or ""),
                "role": str(user.get("role") or ""),
                "permissions": perms,
                "expires_at": expires,
            },
        }

    @router.get("/admin/api/auth/me")
    def api_auth_me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        return {"ok": True, "session": ctx}

    @router.post("/admin/api/auth/logout")
    def api_auth_logout(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        store = SqliteStore(db_path())
        token = _extract_bearer(authorization)
        if token:
            store.revoke_auth_session(session_token_hash=_sha256_hex(token))
        return {"ok": True}

    @router.get("/admin/api/admin-audit")
    def api_admin_audit(
        limit: int = Query(default=200),
        action: str | None = Query(default=None),
        actor_user_id: str | None = Query(default=None),
        status: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        store = SqliteStore(db_path())
        ctx = _resolve_auth(store, authorization)
        _require_permission(ctx, "admin:user:write")
        rows = store.list_admin_audit_logs(tenant_id=str(ctx.get("tenant_id") or ""), limit=limit)
        a = str(action or "").strip()
        actor = str(actor_user_id or "").strip()
        st = str(status or "").strip()
        if a:
            rows = [r for r in rows if str(r.get("action") or "") == a]
        if actor:
            rows = [r for r in rows if str(r.get("actor_user_id") or "") == actor]
        if st:
            rows = [r for r in rows if str(r.get("status") or "") == st]
        return {"ok": True, "items": rows}

    from oclaw.interfaces.admin.chat_api import include_chat_routes
    from oclaw.interfaces.admin.models_api import include_model_mgmt_routes
    from oclaw.interfaces.admin.skills_api import include_skill_routes

    include_chat_routes(router, resolve_auth=_resolve_auth)
    include_model_mgmt_routes(router, resolve_auth=_resolve_auth)
    include_skill_routes(router, resolve_auth=_resolve_auth)

    return router


__all__ = ["build_admin_router", "admin_static_dir"]

