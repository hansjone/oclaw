"""工具目录聚合与默认注册入口。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from interfaces.gateway.python_extensions_loader import build_python_extensions_registry
from svc.config.paths import PROJECT_ROOT
from runtime.tools.base import ToolRegistry, ToolSpec
from runtime.tools.expert_registry import materialize_tools_for_expert
from runtime.tools.mcp.adapter import materialize_mcp_tools_for_specialist
from runtime.tools.public_registry import materialize_public_tools
from runtime.tools.skills_runtime.materialize_skill_tools import materialize_executable_skill_tools
from runtime.skills import SkillSpec, materialize_skills_from_tool_specs

logger = logging.getLogger(__name__)
# Tools hidden from model-facing registry to enforce auto-install only policy.
_MODEL_TOOLS_DENYLIST = frozenset(
    {
        "skill_market_install",
        "skill_registry_install",
    }
)

# Legacy export: some modules still import TOOL_FACTORIES. Tools are now intentionally
# restricted to a single safe builtin (`system_time`), so this is left empty.
TOOL_FACTORIES: tuple[object, ...] = ()

def _is_truthy(v: str | None) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def _skill_toolcall_enabled(store: SqliteStore | None) -> bool:
    try:
        raw_env = str(os.getenv("AIA_SKILL_TOOLCALL_ENABLED") or "").strip()
        if raw_env:
            return _is_truthy(raw_env)
        if store is not None:
            raw = str(store.get_setting("AIA_SKILL_TOOLCALL_ENABLED") or "").strip()
            if raw:
                return _is_truthy(raw)
    except Exception:
        pass
    # Default off: skill uses prompt-injection path, not toolcall path.
    return False


def _apply_declared_tool_policy(
    tools: list[ToolSpec],
    *,
    allow_tags: list[str] | tuple[str, ...] | None = None,
    allow_tools: list[str] | tuple[str, ...] | None = None,
) -> list[ToolSpec]:
    tags = {str(x or "").strip().lower() for x in (allow_tags or []) if str(x or "").strip()}
    names = {str(x or "").strip() for x in (allow_tools or []) if str(x or "").strip()}
    if not tags and not names:
        return tools
    out: list[ToolSpec] = []
    for t in tools:
        tname = str(t.name or "")
        ttags = {str(x or "").strip().lower() for x in set(t.tags or frozenset())}
        by_name = tname in names
        by_tag = bool(tags.intersection(ttags))
        if by_name or by_tag:
            out.append(t)
    return out


def _normalize_tool_name(name: str) -> str:
    return str(name or "").strip()


def _source_rank(source: str) -> int:
    # Higher rank wins when names conflict.
    order = {
        "expert": 50,
        "public": 40,
        "skill_runtime": 30,
        "mcp": 20,
        "plugin": 10,
    }
    return int(order.get(str(source or "").strip().lower(), 0))


def _resolve_tool_conflicts(collected: list[tuple[str, ToolSpec]]) -> list[ToolSpec]:
    chosen: dict[str, tuple[str, ToolSpec]] = {}
    for source, spec in collected:
        name = _normalize_tool_name(getattr(spec, "name", ""))
        if not name:
            continue
        prev = chosen.get(name)
        if prev is None:
            chosen[name] = (source, spec)
            continue
        prev_source, prev_spec = prev
        cur_risk = str(getattr(spec, "risk_level", "low") or "low").strip().lower()
        prev_risk = str(getattr(prev_spec, "risk_level", "low") or "low").strip().lower()
        cur_rank = _source_rank(source)
        prev_rank = _source_rank(prev_source)
        # Prefer lower risk first; if equal risk, prefer stronger source rank.
        if (cur_risk == "low" and prev_risk != "low") or (
            cur_risk == prev_risk and cur_rank >= prev_rank
        ):
            chosen[name] = (source, spec)
    # Preserve deterministic order by first collection order.
    output: list[ToolSpec] = []
    seen: set[str] = set()
    for _, spec in collected:
        name = _normalize_tool_name(getattr(spec, "name", ""))
        if not name or name in seen:
            continue
        final = chosen.get(name)
        if final is None:
            continue
        output.append(final[1])
        seen.add(name)
    return output


def materialize_tool_specs(
    factories: tuple[ToolFactory, ...] | None = None,
    *,
    expert: str | None = None,
    specialist: str | None = None,
    policy_session_id: str | None = None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
    store: SqliteStore | None = None,
) -> list[ToolSpec]:
    """Materialize ToolSpec list.

    Base tools are loaded from self-registered expert tool directories (role-aware by `expert`),
    plus public shared tools available to all roles.
    """
    _ = factories
    collected: list[tuple[str, ToolSpec]] = []

    def _hidden_from_model(name: str) -> bool:
        return str(name or "").strip() in _MODEL_TOOLS_DENYLIST

    def _risk_allowed(spec: ToolSpec) -> bool:
        # Optional safety gate for public tools.
        # Default: only allow low risk public tools to be visible to all roles.
        # Override via env: AIA_PUBLIC_TOOLS_ALLOW_HIGH=1 to allow high risk public tools.
        # If env is unset, fallback to per-user workspace path policy switch.
        raw_env = str(os.getenv("AIA_PUBLIC_TOOLS_ALLOW_HIGH") or "").strip()
        if raw_env:
            allow_high = _is_truthy(raw_env)
        else:
            allow_high = False
            try:
                if store is not None and path_policy_tenant_id and path_policy_user_id:
                    row = store.get_user_workspace_path_allowlist(
                        tenant_id=str(path_policy_tenant_id),
                        user_id=str(path_policy_user_id),
                    )
                    allow_high = bool((row or {}).get("allow_high_risk_public_tools"))
            except Exception:
                allow_high = False
        if allow_high:
            return True
        return str(getattr(spec, "risk_level", "") or "low").strip().lower() != "high"

    # collect: public
    try:
        for spec in list(materialize_public_tools()):
            if not isinstance(spec, ToolSpec):
                continue
            if _hidden_from_model(str(spec.name or "")):
                logger.info("public tool hidden from model registry: %s", str(spec.name or ""))
                continue
            if not _risk_allowed(spec):
                logger.warning("public tool blocked by risk gate: %s", str(spec.name or ""))
                continue
            collected.append(("public", spec))
    except Exception as exc:
        logger.warning("public tool load skipped: %s", exc)

    # collect: expert
    try:
        for spec in materialize_tools_for_expert(str(expert or "").strip() or None):
            if not isinstance(spec, ToolSpec):
                continue
            if _hidden_from_model(str(spec.name or "")):
                logger.info("expert tool hidden from model registry: %s", str(spec.name or ""))
                continue
            collected.append(("expert", spec))
    except Exception as exc:
        logger.warning("expert tool load skipped: %s", exc)

    # collect: skill runtime
    if _skill_toolcall_enabled(store):
        try:
            for spec in materialize_executable_skill_tools(store=store):
                if not isinstance(spec, ToolSpec):
                    continue
                if _hidden_from_model(str(spec.name or "")):
                    logger.info("skill runtime tool hidden from model registry: %s", str(spec.name or ""))
                    continue
                collected.append(("skill_runtime", spec))
        except Exception as exc:
            logger.warning("skill runtime tool load skipped: %s", exc)

    # MCP tools are role-bound and should be materialized before model injection.
    # Fine-grained penalty/visibility is still applied by wire policy in direct_loop.
    mcp_enabled = True
    try:
        if store is not None:
            raw = str(store.get_setting("AIA_ENABLE_MCP_TOOLS") or "").strip().lower()
            if raw:
                mcp_enabled = raw in {"1", "true", "yes", "on"}
    except Exception:
        mcp_enabled = True
    # collect: mcp
    if mcp_enabled and _is_truthy(os.getenv("AIA_ENABLE_MCP_TOOLS", "1")):
        try:
            for spec in materialize_mcp_tools_for_specialist(
                store=store,
                specialist=str(specialist or "").strip().lower() or None,
                policy_session_id=policy_session_id,
                path_policy_tenant_id=path_policy_tenant_id,
                path_policy_user_id=path_policy_user_id,
            ):
                if isinstance(spec, ToolSpec):
                    if _hidden_from_model(str(spec.name or "")):
                        logger.info("mcp tool hidden from model registry: %s", str(spec.name or ""))
                        continue
                    collected.append(("mcp", spec))
        except Exception as exc:
            logger.warning("mcp tool load skipped: %s", exc)

    # collect: plugin
    if not _is_truthy(os.getenv("AIA_PLUGIN_TOOLS_ENABLED", "1")):
        return _resolve_tool_conflicts(collected)

    try:
        only_ids_raw = str(os.getenv("AIA_PLUGIN_TOOL_IDS") or "").strip()
        only_ids = [x.strip() for x in only_ids_raw.split(",") if x.strip()] if only_ids_raw else []
        ws_dir = Path(PROJECT_ROOT).resolve()
        app_cfg: dict[str, Any] = {}
        if store is not None:
            try:
                app_cfg = dict(store.load_oclaw_config() or {})
            except Exception:
                app_cfg = {}
        plugin_registry = build_python_extensions_registry(
            app_config=app_cfg,
            workspace_dir=str(ws_dir),
            only_plugin_ids=only_ids,
        )
        for row in list(plugin_registry.get("tools") or []):
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            handler = row.get("handler")
            params = row.get("parameters")
            if not name or not callable(handler) or not isinstance(params, dict):
                continue
            tags_raw = row.get("tags")
            tags = frozenset(str(x).strip() for x in (tags_raw or []) if str(x).strip())
            if _hidden_from_model(name):
                logger.info("plugin tool hidden from model registry: %s", name)
                continue
            collected.append((
                "plugin",
                ToolSpec(
                    name=name,
                    description=str(row.get("description") or ""),
                    parameters=params,
                    handler=handler,
                    tags=tags,
                    risk_level=str(row.get("risk_level") or "low"),
                    timeout_s=float(row.get("timeout_s")) if row.get("timeout_s") is not None else None,
                    read_only=bool(row.get("read_only", False)),
                )
            ))
    except Exception as exc:
        logger.warning("plugin tool load skipped: %s", exc)
    # normalize/policy/resolve_conflict/finalize
    return _resolve_tool_conflicts(collected)


def default_registry(
    *,
    expert: str | None = None,
    specialist: str | None = None,
    policy_session_id: str | None = None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
    store: SqliteStore | None = None,
    allow_tags: list[str] | tuple[str, ...] | None = None,
    allow_tools: list[str] | tuple[str, ...] | None = None,
) -> ToolRegistry:
    tools = materialize_tool_specs(
        expert=expert,
        specialist=specialist,
        policy_session_id=policy_session_id,
        path_policy_tenant_id=path_policy_tenant_id,
        path_policy_user_id=path_policy_user_id,
        store=store,
    )
    tools = _apply_declared_tool_policy(tools, allow_tags=allow_tags, allow_tools=allow_tools)
    return ToolRegistry(tools)


def materialize_skills(
    *,
    expert: str | None = None,
    specialist: str | None = None,
    policy_session_id: str | None = None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
    store: SqliteStore | None = None,
) -> tuple[SkillSpec, ...]:
    tools = materialize_tool_specs(
        expert=expert,
        specialist=specialist,
        policy_session_id=policy_session_id,
        path_policy_tenant_id=path_policy_tenant_id,
        path_policy_user_id=path_policy_user_id,
        store=store,
    )
    return materialize_skills_from_tool_specs(tools)


def tool_inventory() -> list[dict[str, Any]]:
    """返回每个已注册工具的 ``name`` 与 ``tags``（用于文档、测试或后续管理界面）。"""
    rows: list[dict[str, Any]] = []
    for spec in materialize_tool_specs():
        rows.append({"name": spec.name, "tags": sorted(spec.tags)})
    return rows


__all__ = [
    "_apply_declared_tool_policy",
    "default_registry",
    "materialize_skills",
    "materialize_tool_specs",
    "tool_inventory",
]
