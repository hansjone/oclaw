from __future__ import annotations

from pathlib import Path
from typing import Any

from oclaw.platform.config.paths import db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.skill_installer import auto_install_skill_from_payload, install_skill_from_registry_archive
from oclaw.runtime.skills import default_skills_root
from oclaw.runtime.skills_market import get_market_adapter, normalize_skill_market_provider_setting
from oclaw.runtime.tools.base import ToolSpec


def _store() -> SqliteStore:
    return SqliteStore(db_path())


def _agent_workspace_skills_root() -> Path:
    return default_skills_root() / "_workspace"


def skill_auto_install_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        payload = args if isinstance(args, dict) else {}
        store = _store()
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
                skills_root=_agent_workspace_skills_root(),
                auto_bind=True,
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
        out = auto_install_skill_from_payload(store=store, payload=skill_payload)
        return {
            "ok": bool(out.ok),
            "name": out.name,
            "target_dir": out.target_dir,
            "detail": out.detail,
            "error_code": out.error_code,
            "retryable": bool(out.retryable),
            "auto_enabled": bool(getattr(out, "auto_enabled", False)),
            "binding_applied_roles": list(getattr(out, "binding_applied_roles", ()) or []),
        }

    return ToolSpec(
        name="skill_auto_install",
        description="Auto install a skill into _workspace lane (payload or market/archive).",
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
