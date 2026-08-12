from __future__ import annotations

import threading
import time
from typing import Any

from svc.persistence.assistant_store import get_assistant_store
from runtime.agent_context import build_role_system_context
from runtime.agents.specialists import discover_specialist_ids
from runtime.direct_loop import tool_wire_freeze_status, warm_tool_wire_cache
from runtime.system_prompt import get_executor_prompt_static, warm_executor_prompt_cache
from runtime.tools.catalog import default_registry

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


def get_manager_prompt_prebuild(
    *,
    store: Any,
    registry: Any,
    base_url: str,
    memory_enabled: bool,
) -> dict[str, Any]:
    """Legacy stub: Manager prompt packing removed; return specialist catalog only."""
    del store, registry, base_url
    allowed_fixed = [str(x).strip().lower() for x in discover_specialist_ids() if str(x).strip()]
    if not allowed_fixed:
        allowed_fixed = ["generalist"]
    if not memory_enabled:
        allowed_fixed = [x for x in allowed_fixed if x != "memory"]
    if "generalist" not in allowed_fixed:
        allowed_fixed.insert(0, "generalist")
    allowed_fixed_quoted = ", ".join([f'"{x}"' for x in allowed_fixed])
    return {
        "manager_context": "",
        "allowed_fixed": tuple(allowed_fixed),
        "allowed_fixed_quoted": allowed_fixed_quoted,
    }


def warm_startup_prompt_prebuild(*, store: Any, registry: Any, base_url: str, memory_enabled: bool) -> dict[str, Any]:
    del memory_enabled
    t0 = time.perf_counter()
    role_systems: dict[str, str] = {}
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
        "manager_candidates": 0,
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
    own_store = store if store is not None else get_assistant_store()
    try:
        from runtime.operations.mcp_env import apply_gateway_mcp_env_to_os
        from runtime.tools.mcp.sync_tools import sync_enabled_mcp_servers

        try:
            apply_gateway_mcp_env_to_os()
        except Exception:
            pass
        # Refresh MCP tool catalogs first so wire freeze/prewarm sees current tools/list.
        # Health is best-effort and does not gate sync (wire penalty/suppression was removed).
        mcp_sync = sync_enabled_mcp_servers(own_store)
        registry = default_registry(store=own_store)
        prompt_stats = warm_startup_prompt_prebuild(
            store=own_store,
            registry=registry,
            base_url=base_url,
            memory_enabled=bool(memory_enabled),
        )
        roles = list(discover_specialist_ids())
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
            "mcp_sync": mcp_sync,
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
    own_store = store if store is not None else get_assistant_store()
    registry = default_registry(store=own_store)
    target = str(role or "").strip().lower()
    if target in {"manager", "manager_self", "main"}:
        target = "generalist"
    allowed_roles = list(discover_specialist_ids())
    if target and target not in allowed_roles:
        return {"ok": False, "error": "invalid_role", "allowed_roles": allowed_roles}
    selected_roles = [target] if target else allowed_roles

    prompts: dict[str, dict[str, Any]] = {}
    for rid in selected_roles:
        base_system = build_role_system_context(str(rid))
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
