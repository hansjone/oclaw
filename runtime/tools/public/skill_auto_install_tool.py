from __future__ import annotations

from pathlib import Path
from typing import Any

from oclaw.platform.config.paths import db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.chat.tool_invocation_context import (
    current_tool_lane_sessions,
    current_tool_workspace_lane_role,
)
from oclaw.runtime.skill_installer import auto_install_skill_from_payload, install_skill_from_registry_archive
from oclaw.runtime.skills_market import get_market_adapter, normalize_skill_market_provider_setting
from oclaw.runtime.skills_workspace_lane import resolve_auto_install_parent
from oclaw.runtime.tools.base import ToolSpec


def _store() -> SqliteStore:
    return SqliteStore(db_path())


def _coerce_public_flag(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on", "public"}


def _agent_skill_install_parent(*, public: bool) -> Path:
    role = current_tool_workspace_lane_role()
    owner, sid = current_tool_lane_sessions()
    return resolve_auto_install_parent(
        public=public,
        workspace_lane_role=role,
        workspace_owner_session_id=owner,
        session_id=sid,
        skills_home=None,
    )


def skill_auto_install_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        payload = args if isinstance(args, dict) else {}
        store = _store()
        public = _coerce_public_flag(payload.get("public"))
        install_parent = _agent_skill_install_parent(public=public)
        lane_role = current_tool_workspace_lane_role()
        auto_bind = bool(public)
        archive_url = str(payload.get("archive_url") or "").strip()
        slug = str(payload.get("slug") or "").strip()
        version = str(payload.get("version") or "").strip() or None
        overwrite = bool(payload.get("overwrite"))
        provider = normalize_skill_market_provider_setting(
            str(payload.get("provider") or store.get_setting("AIA_SKILL_MARKET_PROVIDER") or "")
        )
        if not archive_url and slug:
            try:
                adapter = get_market_adapter(provider)
                archive_url, _chosen_version = adapter.resolve_archive_url(slug=slug, version=version)
            except Exception:
                archive_url = ""
        if archive_url:
            out = install_skill_from_registry_archive(
                store=store,
                archive_url=archive_url,
                overwrite=overwrite,
                skills_root=install_parent,
                auto_bind=auto_bind,
            )
            return {
                "ok": bool(out.ok),
                "name": out.name,
                "target_dir": out.target_dir,
                "detail": out.detail,
                "error_code": out.error_code,
                "retryable": bool(out.retryable),
                "auto_enabled": bool(getattr(out, "auto_enabled", False)),
                "binding_applied_roles": list(getattr(out, "binding_applied_roles", ()) or []),
                "provider": provider,
                "public": public,
                "install_lane": str(install_parent),
                "workspace_lane_role": lane_role,
            }

        skill_payload = {
            "name": str(payload.get("name") or "").strip(),
            "description": str(payload.get("description") or "").strip(),
            "body_markdown": str(payload.get("body_markdown") or "").strip(),
            "metadata_oclaw": dict(payload.get("metadata_oclaw") or {})
            if isinstance(payload.get("metadata_oclaw"), dict)
            else {},
        }
        if not skill_payload["name"]:
            return {"ok": False, "error_code": "name_required", "error": "name_required"}
        if not skill_payload["description"]:
            skill_payload["description"] = f"{skill_payload['name']} skill"
        out = auto_install_skill_from_payload(
            store=store,
            payload=skill_payload,
            workspace_install_parent=install_parent,
            auto_bind=auto_bind,
        )
        return {
            "ok": bool(out.ok),
            "name": out.name,
            "target_dir": out.target_dir,
            "detail": out.detail,
            "error_code": out.error_code,
            "retryable": bool(out.retryable),
            "auto_enabled": bool(getattr(out, "auto_enabled", False)),
            "binding_applied_roles": list(getattr(out, "binding_applied_roles", ()) or []),
            "public": public,
            "install_lane": str(install_parent),
            "workspace_lane_role": lane_role,
        }

    return ToolSpec(
        name="skill_auto_install",
        description=(
            "Auto install a skill under the agent workspace lane. "
            "Use public=true for shared _workspace/public; omit or false for a role folder "
            "sibling to public: _workspace/<skill_binding_role>/ (e.g. generalist, ops)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "body_markdown": {"type": "string"},
                "metadata_oclaw": {"type": "object"},
                "slug": {"type": "string"},
                "provider": {"type": "string"},
                "version": {"type": "string"},
                "archive_url": {"type": "string"},
                "overwrite": {"type": "boolean"},
                "public": {
                    "type": "boolean",
                    "description": "If true, install to shared _workspace/public with role auto-bind; if false, install under this tool run's session lane only.",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"skill", "oclaw", "installer"}),
        risk_level="high",
        timeout_s=120.0,
    )


__all__ = ["skill_auto_install_tool"]
