from __future__ import annotations

import threading
import time
from typing import Any

from oclaw.platform.config.paths import db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.agent_context import build_role_system_context
from oclaw.runtime.agents.specialists import discover_specialist_ids
from oclaw.runtime.direct_loop import tool_wire_freeze_status, warm_tool_wire_cache
from oclaw.runtime.system_prompt import get_executor_prompt_static, warm_executor_prompt_cache
from oclaw.runtime.tools.catalog import default_registry
from oclaw.runtime.workspaces.experts import expert_workspace_signature_token, list_experts

_MANAGER_PREBUILD_CACHE_LOCK = threading.Lock()
_MANAGER_PREBUILD_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_RUNTIME_PREWARM_LOCK = threading.Lock()
_RUNTIME_PREWARM_RUNNING = False
_RUNTIME_PREWARM_LAST: dict[str, Any] = {
    "ok": False,
    "running": False,
    "reason": "",
    "elapsed_ms": 0,
    "started_at_ms": 0,
    "finished_at_ms": 0,
    "error": "",
}
_RUNTIME_PREWARM_HISTORY: list[dict[str, Any]] = []
_RUNTIME_PREWARM_HISTORY_LIMIT = 40


def _manager_settings_signature(store: Any) -> tuple[str, ...]:
    keys = (
        "AIA_SKILL_RUNTIME_ENABLED",
        "AIA_SKILL_DISABLED_NAMES",
        "AIA_SKILL_ROLE_BINDING_ENABLED",
        "AIA_SKILL_ROLE_BINDING_MANAGER_INHERIT",
        "AIA_CHAT_SPECIALIST_FLAGS_JSON",
    )
    parts: list[str] = []
    for key in keys:
        try:
            val = str(store.get_setting(key) or "")
        except Exception:
            val = ""
        parts.append(f"{key}={val}")
    return tuple(parts)


def _compact_line(text: str, *, limit: int = 80) -> str:
    s = " ".join(str(text or "").strip().split())
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 1)] + "…"


def _build_expert_desc_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for row in list_experts():
        eid = str(row.get("id") or "").strip().lower()
        if not eid:
            continue
        files = row.get("files") if isinstance(row, dict) else {}
        if not isinstance(files, dict):
            continue
        desc = _compact_line(str(files.get("ROLE_SYSTEM.md") or ""), limit=80)
        if desc:
            out[eid] = desc
    return out


def get_manager_prompt_prebuild(
    *,
    store: Any,
    registry: Any,
    base_url: str,
    memory_enabled: bool,
) -> dict[str, Any]:
    cache_key = (
        str(base_url or "").strip(),
        bool(memory_enabled),
        expert_workspace_signature_token(),
        _manager_settings_signature(store),
    )
    with _MANAGER_PREBUILD_CACHE_LOCK:
        cached = _MANAGER_PREBUILD_CACHE.get(cache_key)
    if isinstance(cached, dict):
        return dict(cached)

    allowed_fixed = [str(x).strip().lower() for x in discover_specialist_ids() if str(x).strip()]
    if not allowed_fixed:
        allowed_fixed = ["generalist"]
    if not memory_enabled:
        allowed_fixed = [x for x in allowed_fixed if x != "memory"]
    if "generalist" not in allowed_fixed:
        allowed_fixed.insert(0, "generalist")
    allowed_fixed_quoted = ", ".join([f'"{x}"' for x in allowed_fixed])

    desc_by_id = _build_expert_desc_map()
    candidate_lines = [f"- {sid}: {desc_by_id.get(sid) or 'no description'}" for sid in allowed_fixed]
    dynamic_hint = (
        f"\n{chr(10).join(candidate_lines)}\n"
        "不要假设固定专家集合。"
    )
    manager_context = build_role_system_context(
        "manager",
        template_vars={"MANAGER_DYNAMIC_EXPERTS_HINT": dynamic_hint},
    )
    out = {
        "manager_context": manager_context,
        "allowed_fixed": tuple(allowed_fixed),
        "allowed_fixed_quoted": allowed_fixed_quoted,
    }
    with _MANAGER_PREBUILD_CACHE_LOCK:
        _MANAGER_PREBUILD_CACHE[cache_key] = dict(out)
        if len(_MANAGER_PREBUILD_CACHE) > 64:
            _MANAGER_PREBUILD_CACHE.clear()
    return out


def warm_startup_prompt_prebuild(*, store: Any, registry: Any, base_url: str, memory_enabled: bool) -> dict[str, Any]:
    t0 = time.perf_counter()
    manager_pack = get_manager_prompt_prebuild(
        store=store,
        registry=registry,
        base_url=base_url,
        memory_enabled=memory_enabled,
    )
    role_systems: dict[str, str] = {"manager": str(manager_pack.get("manager_context") or "")}
    for sid in discover_specialist_ids():
        role_systems[str(sid)] = build_role_system_context(str(sid))
    role_warm = warm_executor_prompt_cache(
        store=store,
        tools=registry,
        base_url=base_url,
        role_base_systems=role_systems,
        workspace_dir=None,
    )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "ok": True,
        "elapsed_ms": elapsed_ms,
        "manager_candidates": int(len(manager_pack.get("allowed_fixed") or [])),
        "roles_warmed": int(role_warm.get("roles_warmed") or 0),
    }


def run_runtime_prewarm(
    *,
    reason: str = "manual",
    store: Any | None = None,
    base_url: str = "",
    memory_enabled: bool = True,
) -> dict[str, Any]:
    global _RUNTIME_PREWARM_RUNNING, _RUNTIME_PREWARM_LAST, _RUNTIME_PREWARM_HISTORY
    with _RUNTIME_PREWARM_LOCK:
        if _RUNTIME_PREWARM_RUNNING:
            return {
                "ok": False,
                "running": True,
                "error": "prewarm_running",
                "reason": str(reason or ""),
                "status": dict(_RUNTIME_PREWARM_LAST),
            }
        _RUNTIME_PREWARM_RUNNING = True
        started_at_ms = int(time.time() * 1000)
        _RUNTIME_PREWARM_LAST = {
            "ok": False,
            "running": True,
            "reason": str(reason or ""),
            "elapsed_ms": 0,
            "started_at_ms": started_at_ms,
            "finished_at_ms": 0,
            "error": "",
        }
    t0 = time.perf_counter()
    own_store = store if store is not None else SqliteStore(db_path())
    try:
        registry = default_registry(store=own_store)
        prompt_stats = warm_startup_prompt_prebuild(
            store=own_store,
            registry=registry,
            base_url=base_url,
            memory_enabled=bool(memory_enabled),
        )
        roles = ["manager", *list(discover_specialist_ids())]
        tool_stats = warm_tool_wire_cache(
            store=own_store,
            tools=registry,
            base_url=base_url,
            roles=roles,
        )
        freeze = tool_wire_freeze_status(store=own_store)
        out = {
            "ok": True,
            "running": False,
            "reason": str(reason or ""),
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "started_at_ms": started_at_ms,
            "finished_at_ms": int(time.time() * 1000),
            "prompt": prompt_stats,
            "tools": tool_stats,
            "freeze": freeze,
            "error": "",
        }
    except Exception as exc:
        out = {
            "ok": False,
            "running": False,
            "reason": str(reason or ""),
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "started_at_ms": started_at_ms,
            "finished_at_ms": int(time.time() * 1000),
            "error": str(exc),
        }
    with _RUNTIME_PREWARM_LOCK:
        _RUNTIME_PREWARM_RUNNING = False
        _RUNTIME_PREWARM_LAST = dict(out)
        _RUNTIME_PREWARM_HISTORY.insert(0, dict(out))
        if len(_RUNTIME_PREWARM_HISTORY) > _RUNTIME_PREWARM_HISTORY_LIMIT:
            _RUNTIME_PREWARM_HISTORY = _RUNTIME_PREWARM_HISTORY[:_RUNTIME_PREWARM_HISTORY_LIMIT]
    return out


def runtime_prewarm_status(*, store: Any | None = None) -> dict[str, Any]:
    with _RUNTIME_PREWARM_LOCK:
        running = bool(_RUNTIME_PREWARM_RUNNING)
        last = dict(_RUNTIME_PREWARM_LAST)
        history = [dict(x) for x in _RUNTIME_PREWARM_HISTORY]
    freeze = tool_wire_freeze_status(store=store) if store is not None else tool_wire_freeze_status()
    return {"ok": True, "running": running, "last": last, "history": history, "freeze": freeze}


def runtime_prewarm_prompts_snapshot(
    *,
    store: Any | None = None,
    role: str | None = None,
    base_url: str = "",
    memory_enabled: bool = True,
) -> dict[str, Any]:
    own_store = store if store is not None else SqliteStore(db_path())
    registry = default_registry(store=own_store)
    target = str(role or "").strip().lower()
    allowed_roles = ["manager", *list(discover_specialist_ids())]
    if target and target not in allowed_roles:
        return {"ok": False, "error": "invalid_role", "allowed_roles": allowed_roles}
    selected_roles = [target] if target else allowed_roles

    manager_pack = get_manager_prompt_prebuild(
        store=own_store,
        registry=registry,
        base_url=base_url,
        memory_enabled=memory_enabled,
    )
    prompts: dict[str, dict[str, Any]] = {}
    for rid in selected_roles:
        base_system = (
            str(manager_pack.get("manager_context") or "")
            if rid == "manager"
            else build_role_system_context(str(rid))
        )
        executor_system = get_executor_prompt_static(
            store=own_store,
            tools=registry,
            base_url=base_url,
            base_system=base_system,
            workspace_dir=None,
            skill_binding_role=str(rid),
        )
        # Unified snapshot key for all roles.
        item: dict[str, Any] = {
            "system_prompt": executor_system,
        }
        prompts[str(rid)] = item
    return {"ok": True, "roles": selected_roles, "prompts": prompts}


__all__ = [
    "get_manager_prompt_prebuild",
    "run_runtime_prewarm",
    "runtime_prewarm_prompts_snapshot",
    "runtime_prewarm_status",
    "warm_startup_prompt_prebuild",
]
