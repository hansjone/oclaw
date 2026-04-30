from __future__ import annotations

from pathlib import Path
from typing import Any

from oclaw.platform.config.paths import db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.skill_installer import install_skill_from_registry_archive
from oclaw.runtime.skills import default_skills_root
from oclaw.runtime.skills_market import get_market_adapter, normalize_skill_market_provider_setting
from oclaw.runtime.tools.base import ToolSpec


def _store() -> SqliteStore:
    return SqliteStore(db_path())


def _agent_workspace_skills_root() -> Path:
    # Agent-origin installs are isolated under _workspace lane.
    return default_skills_root() / "_workspace"


def skill_market_install_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        payload = args if isinstance(args, dict) else {}
        slug = str(payload.get("slug") or "").strip()
        if not slug:
            return {"ok": False, "error_code": "slug_required", "error": "slug_required"}
        version = str(payload.get("version") or "").strip() or None
        overwrite = bool(payload.get("overwrite"))
        store = _store()
        provider_arg = str(payload.get("provider") or "").strip()
        if provider_arg:
            provider = normalize_skill_market_provider_setting(provider_arg)
        else:
            provider = normalize_skill_market_provider_setting(str(store.get_setting("AIA_SKILL_MARKET_PROVIDER") or ""))
        try:
            adapter = get_market_adapter(provider)
            archive_url, chosen_version = adapter.resolve_archive_url(slug=slug, version=version)
        except Exception as exc:
            return {
                "ok": False,
                "error_code": "market_resolve_failed",
                "error": f"market_resolve_failed:{type(exc).__name__}",
                "provider": provider,
                "slug": slug,
            }
        if not str(archive_url or "").strip():
            return {
                "ok": False,
                "error_code": "archive_url_unavailable",
                "error": "archive_url_unavailable",
                "provider": provider,
                "slug": slug,
            }
        out = install_skill_from_registry_archive(
            store=store,
            archive_url=str(archive_url),
            overwrite=overwrite,
            skills_root=_agent_workspace_skills_root(),
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
            "provider": provider,
            "slug": slug,
            "version": str(chosen_version or version or ""),
        }

    return ToolSpec(
        name="skill_market_install",
        description="Install a skill from configured market by slug/version.",
        parameters={
            "type": "object",
            "properties": {
                "slug": {"type": "string"},
                "provider": {"type": "string", "description": "Optional provider override: clawhub or cocoloop."},
                "version": {"type": "string"},
                "overwrite": {"type": "boolean"},
            },
            "required": ["slug"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"skill", "installer", "market"}),
        risk_level="medium",
        timeout_s=120.0,
    )


def skill_registry_install_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        payload = args if isinstance(args, dict) else {}
        archive_url = str(payload.get("archive_url") or "").strip()
        if not archive_url:
            return {"ok": False, "error_code": "archive_url_required", "error": "archive_url_required"}
        overwrite = bool(payload.get("overwrite"))
        out = install_skill_from_registry_archive(
            store=_store(),
            archive_url=archive_url,
            overwrite=overwrite,
            skills_root=_agent_workspace_skills_root(),
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

    return ToolSpec(
        name="skill_registry_install",
        description="Install a skill from archive URL (registry/market artifact).",
        parameters={
            "type": "object",
            "properties": {
                "archive_url": {"type": "string"},
                "overwrite": {"type": "boolean"},
            },
            "required": ["archive_url"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"skill", "installer", "registry"}),
        risk_level="medium",
        timeout_s=120.0,
    )


__all__ = ["skill_market_install_tool", "skill_registry_install_tool"]

