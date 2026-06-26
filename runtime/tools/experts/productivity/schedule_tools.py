from __future__ import annotations

import json
from typing import Any

from runtime.scheduler.cron_service import build_delivery_for_session
from runtime.scheduler.expressions import normalize_schedule_kind
from runtime.scheduler.service import run_scheduled_job_now
from runtime.types import normalize_interaction_mode, normalize_requested_specialist
from svc.persistence.assistant_store import get_assistant_store
from runtime.tools.base import ToolSpec
from runtime.tools.context_inject import enrich_tool_arguments


def _require(s: str, name: str) -> str:
    v = (s or "").strip()
    if not v:
        raise ValueError(f"{name} is required")
    return v


def _parse_delivery_arg(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    return None


def schedule_create_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            store = get_assistant_store()
            args = enrich_tool_arguments(
                store=store,
                session_id=str(args.get("session_id") or ""),
                tool_name="schedule_create",
                arguments=args,
            )
            tenant_id = _require(str(args.get("tenant_id") or ""), "tenant_id")
            owner_user_id = _require(
                str(args.get("owner_user_id") or args.get("user_id") or ""),
                "owner_user_id",
            )
            name = _require(str(args.get("name") or ""), "name")
            prompt_text = _require(str(args.get("prompt_text") or ""), "prompt_text")
            schedule_kind = normalize_schedule_kind(str(args.get("schedule_kind") or "cron"))
            schedule_expr = _require(str(args.get("schedule_expr") or ""), "schedule_expr")
            delivery = _parse_delivery_arg(args.get("delivery"))
            if delivery is None:
                delivery = build_delivery_for_session(
                    store,
                    tenant_id=tenant_id,
                    session_id=str(args.get("session_id") or ""),
                    whatsapp_chat_id=str(args.get("whatsapp_chat_id") or ""),
                )
            interaction_mode = normalize_interaction_mode(
                str(args.get("interaction_mode") or "expert")
            )
            specialist = normalize_requested_specialist(
                str(args.get("specialist") or args.get("selected_specialist") or "generalist")
            )
            row = store.scheduled_job_create(
                tenant_id=tenant_id,
                name=name,
                prompt_text=prompt_text,
                schedule_kind=schedule_kind,
                schedule_expr=schedule_expr,
                timezone_name=str(args.get("timezone") or "Asia/Shanghai"),
                description=str(args.get("description") or ""),
                interaction_mode=interaction_mode,
                specialist=specialist,
                lang=str(args.get("lang") or "zh"),
                delivery=delivery,
                source_session_id=str(args.get("session_id") or "").strip() or None,
                created_by_user_id=owner_user_id,
                source="chat",
            )
            return {"ok": True, "job": store.scheduled_job_to_dict(row)}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="schedule_create",
        description="Create a scheduled job (cron, once, or interval). Delivery follows the current chat channel (WhatsApp vs WeChat) unless delivery is set explicitly.",
        parameters={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string", "description": "Auto-filled from session; do not guess."},
                "owner_user_id": {"type": "string", "description": "Auto-filled from session."},
                "session_id": {"type": "string", "description": "Auto-filled from session."},
                "name": {"type": "string"},
                "prompt_text": {"type": "string"},
                "schedule_kind": {"type": "string", "enum": ["cron", "once", "interval"]},
                "schedule_expr": {"type": "string"},
                "timezone": {"type": "string", "default": "Asia/Shanghai"},
                "interaction_mode": {"type": "string"},
                "specialist": {"type": "string"},
                "selected_specialist": {"type": "string"},
                "lang": {"type": "string"},
                "whatsapp_chat_id": {"type": "string"},
                "delivery": {"type": "object"},
                "description": {"type": "string"},
            },
            "required": ["name", "prompt_text", "schedule_kind", "schedule_expr"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "write", "schedule"}),
    )


def schedule_list_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            store = get_assistant_store()
            args = enrich_tool_arguments(
                store=store,
                session_id=str(args.get("session_id") or ""),
                tool_name="schedule_list",
                arguments=args,
            )
            tenant_id = _require(str(args.get("tenant_id") or ""), "tenant_id")
            status = str(args.get("status") or "").strip() or None
            limit = int(args.get("limit") or 50)
            rows = store.scheduled_job_list(tenant_id=tenant_id, status=status, limit=limit)
            return {"ok": True, "items": [store.scheduled_job_to_dict(r) for r in rows]}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="schedule_list",
        description="List scheduled jobs for a tenant.",
        parameters={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},
                "status": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "schedule"}),
    )


def _scoped_args(store: Any, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    return enrich_tool_arguments(
        store=store,
        session_id=str(args.get("session_id") or ""),
        tool_name=tool_name,
        arguments=args,
    )


def schedule_update_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            store = get_assistant_store()
            args = _scoped_args(store, "schedule_update", args)
            tenant_id = _require(str(args.get("tenant_id") or ""), "tenant_id")
            job_id = _require(str(args.get("job_id") or ""), "job_id")
            patch: dict[str, Any] = {}
            for key in (
                "name",
                "description",
                "prompt_text",
                "schedule_kind",
                "schedule_expr",
                "timezone",
                "interaction_mode",
                "specialist",
                "lang",
            ):
                if key in args and args.get(key) is not None:
                    patch[key] = args.get(key)
            delivery = _parse_delivery_arg(args.get("delivery"))
            if delivery is not None:
                patch["delivery"] = delivery
            row = store.scheduled_job_update(tenant_id=tenant_id, job_id=job_id, patch=patch)
            if not row:
                return {"ok": False, "error": "job_not_found"}
            return {"ok": True, "job": store.scheduled_job_to_dict(row)}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="schedule_update",
        description="Update a scheduled job.",
        parameters={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},
                "job_id": {"type": "string"},
                "name": {"type": "string"},
                "prompt_text": {"type": "string"},
                "schedule_kind": {"type": "string"},
                "schedule_expr": {"type": "string"},
                "timezone": {"type": "string"},
                "interaction_mode": {"type": "string"},
                "specialist": {"type": "string"},
                "lang": {"type": "string"},
                "delivery": {"type": "object"},
                "description": {"type": "string"},
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "write", "schedule"}),
    )


def schedule_pause_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            store = get_assistant_store()
            args = _scoped_args(store, "schedule_pause", args)
            tenant_id = _require(str(args.get("tenant_id") or ""), "tenant_id")
            job_id = _require(str(args.get("job_id") or ""), "job_id")
            ok = store.scheduled_job_set_status(tenant_id=tenant_id, job_id=job_id, status="paused")
            return {"ok": bool(ok), "job_id": job_id, "status": "paused"}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="schedule_pause",
        description="Pause a scheduled job.",
        parameters={
            "type": "object",
            "properties": {"tenant_id": {"type": "string"}, "job_id": {"type": "string"}},
            "required": ["job_id"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "write", "schedule"}),
    )


def schedule_resume_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            store = get_assistant_store()
            args = _scoped_args(store, "schedule_resume", args)
            tenant_id = _require(str(args.get("tenant_id") or ""), "tenant_id")
            job_id = _require(str(args.get("job_id") or ""), "job_id")
            ok = store.scheduled_job_set_status(tenant_id=tenant_id, job_id=job_id, status="active")
            return {"ok": bool(ok), "job_id": job_id, "status": "active"}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="schedule_resume",
        description="Resume a paused scheduled job.",
        parameters={
            "type": "object",
            "properties": {"tenant_id": {"type": "string"}, "job_id": {"type": "string"}},
            "required": ["job_id"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "write", "schedule"}),
    )


def schedule_delete_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            store = get_assistant_store()
            args = _scoped_args(store, "schedule_delete", args)
            tenant_id = _require(str(args.get("tenant_id") or ""), "tenant_id")
            job_id = _require(str(args.get("job_id") or ""), "job_id")
            ok = store.scheduled_job_delete(tenant_id=tenant_id, job_id=job_id)
            return {"ok": bool(ok), "job_id": job_id}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="schedule_delete",
        description="Delete (soft) a scheduled job.",
        parameters={
            "type": "object",
            "properties": {"tenant_id": {"type": "string"}, "job_id": {"type": "string"}},
            "required": ["job_id"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "write", "schedule"}),
    )


def schedule_run_now_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            store = get_assistant_store()
            args = _scoped_args(store, "schedule_run_now", args)
            tenant_id = _require(str(args.get("tenant_id") or ""), "tenant_id")
            job_id = _require(str(args.get("job_id") or ""), "job_id")
            out = run_scheduled_job_now(store, tenant_id=tenant_id, job_id=job_id)
            return out
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="schedule_run_now",
        description="Trigger a scheduled job immediately.",
        parameters={
            "type": "object",
            "properties": {"tenant_id": {"type": "string"}, "job_id": {"type": "string"}},
            "required": ["job_id"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "write", "schedule"}),
    )


__all__ = [
    "schedule_create_tool",
    "schedule_list_tool",
    "schedule_update_tool",
    "schedule_pause_tool",
    "schedule_resume_tool",
    "schedule_delete_tool",
    "schedule_run_now_tool",
]
