"""工具目录聚合与默认注册入口。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from oclaw.gateway.python_extensions_loader import build_python_extensions_registry
from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.tools.base import ToolRegistry, ToolSpec
from oclaw.tools.expert_registry import materialize_tools_for_expert
from oclaw.tools.mcp.adapter import materialize_mcp_tools_for_specialist
from oclaw.tools.public_registry import materialize_public_tools
from oclaw.tools.skills_runtime.materialize_skill_tools import materialize_executable_skill_tools
from oclaw.openclaw_runtime.skills import SkillSpec, materialize_skills_from_tool_specs

logger = logging.getLogger(__name__)

# Legacy export: some modules still import TOOL_FACTORIES. Tools are now intentionally
# restricted to a single safe builtin (`system_time`), so this is left empty.
TOOL_FACTORIES: tuple[object, ...] = ()


def _is_truthy(v: str | None) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


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


def _skill_management_tools(store: SqliteStore) -> list[ToolSpec]:
    def _create_skill_handler(args: dict[str, Any]) -> dict[str, Any]:
        out = create_skill_from_template(
            store=store,
            name=str(args.get("name") or "").strip(),
            description=str(args.get("description") or "").strip(),
            body_markdown=str(args.get("body_markdown") or "").strip(),
            metadata_openclaw=dict(args.get("metadata_openclaw") or {}) if isinstance(args.get("metadata_openclaw"), dict) else {},
            overwrite=bool(args.get("overwrite")),
        )
        return {"ok": bool(out.ok), "name": out.name, "target_dir": out.target_dir, "detail": out.detail}

    def _auto_install_skill_handler(args: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "name": str(args.get("name") or "").strip(),
            "description": str(args.get("description") or "").strip(),
            "body_markdown": str(args.get("body_markdown") or "").strip(),
            "metadata_openclaw": dict(args.get("metadata_openclaw") or {}) if isinstance(args.get("metadata_openclaw"), dict) else {},
        }
        out = auto_install_skill_from_payload(store=store, payload=payload)
        return {"ok": bool(out.ok), "name": out.name, "target_dir": out.target_dir, "detail": out.detail}

    def _list_skills_handler(args: dict[str, Any]) -> dict[str, Any]:
        del args
        return {"ok": True, "items": list_skills_with_status(store=store)}

    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
            "body_markdown": {"type": "string"},
            "metadata_openclaw": {"type": "object"},
            "overwrite": {"type": "boolean"},
        },
        "required": ["name", "description"],
    }
    return [
        ToolSpec(
            name="skill_create",
            description="Create a local oclaw skill package from template.",
            parameters=schema,
            handler=_create_skill_handler,
            tags=frozenset({"skill", "openclaw", "builder"}),
            risk_level="high",
            timeout_s=20.0,
        ),
        ToolSpec(
            name="skill_auto_install",
            description="Auto install a generated oclaw skill package.",
            parameters=schema,
            handler=_auto_install_skill_handler,
            tags=frozenset({"skill", "openclaw", "installer"}),
            risk_level="high",
            timeout_s=20.0,
        ),
        ToolSpec(
            name="skill_list",
            description="List installed skills and status.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            handler=_list_skills_handler,
            tags=frozenset({"skill", "openclaw", "read"}),
            read_only=True,
            timeout_s=10.0,
        ),
    ]


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
    tools: list[ToolSpec] = []

    def _risk_allowed(spec: ToolSpec) -> bool:
        # Optional safety gate for public tools.
        # Default: only allow low risk public tools to be visible to all roles.
        # Override via env: AIA_PUBLIC_TOOLS_ALLOW_HIGH=1 to allow high risk public tools.
        allow_high = _is_truthy(os.getenv("AIA_PUBLIC_TOOLS_ALLOW_HIGH", "0"))
        if allow_high:
            return True
        return str(getattr(spec, "risk_level", "") or "low").strip().lower() != "high"

    # Load public shared tools first (available to all roles).
    try:
        for spec in list(materialize_public_tools()):
            if not isinstance(spec, ToolSpec):
                continue
            if not _risk_allowed(spec):
                logger.warning("public tool blocked by risk gate: %s", str(spec.name or ""))
                continue
            tools.append(spec)
    except Exception as exc:
        logger.warning("public tool load skipped: %s", exc)

    # Load role-scoped self-registered internal tools.
    # `expert` can be composite (e.g. "generalist+workspace+productivity"), which
    # is already supported by `materialize_tools_for_expert`.
    try:
        for spec in materialize_tools_for_expert(str(expert or "").strip() or None):
            if not isinstance(spec, ToolSpec):
                continue
            if any(str(t.name or "") == str(spec.name or "") for t in tools):
                continue
            tools.append(spec)
    except Exception as exc:
        logger.warning("expert tool load skipped: %s", exc)

    # Load executable skills (declared via SKILL.md metadata.openclaw.runtime).
    try:
        for spec in materialize_executable_skill_tools(store=store):
            if not isinstance(spec, ToolSpec):
                continue
            if any(str(t.name or "") == str(spec.name or "") for t in tools):
                continue
            tools.append(spec)
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
    if mcp_enabled and _is_truthy(os.getenv("AIA_ENABLE_MCP_TOOLS", "1")):
        try:
            tools.extend(
                materialize_mcp_tools_for_specialist(
                    store=store,
                    specialist=str(specialist or "").strip().lower() or None,
                    policy_session_id=policy_session_id,
                    path_policy_tenant_id=path_policy_tenant_id,
                    path_policy_user_id=path_policy_user_id,
                )
            )
        except Exception as exc:
            logger.warning("mcp tool load skipped: %s", exc)

    if not _is_truthy(os.getenv("AIA_PLUGIN_TOOLS_ENABLED", "1")):
        return tools

    try:
        only_ids_raw = str(os.getenv("AIA_PLUGIN_TOOL_IDS") or "").strip()
        only_ids = [x.strip() for x in only_ids_raw.split(",") if x.strip()] if only_ids_raw else []
        ws_dir = Path(PROJECT_ROOT).resolve()
        app_cfg: dict[str, Any] = {}
        if store is not None:
            try:
                app_cfg = dict(store.load_openclaw_config() or {})
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
            tools.append(
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
            )
    except Exception as exc:
        logger.warning("plugin tool load skipped: %s", exc)
    return tools


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
