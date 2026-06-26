from __future__ import annotations

import json
from typing import Any

from runtime.scheduler.expressions import compute_next_run_at, normalize_schedule_kind
from runtime.scheduler.service import run_scheduled_job_now
from runtime.scheduler.session_resolver import parse_delivery_json, resolve_weixin_binding


class CronService:
    def __init__(self, *, store: Any) -> None:
        self.store = store

    def status(self) -> dict[str, Any]:
        return {"running": True}

    def wake(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, **dict(params or {})}

    def listPage(self, params: dict[str, Any]) -> dict[str, Any]:
        tenant_id = str((params or {}).get("tenantId") or (params or {}).get("tenant_id") or "default").strip()
        status = str((params or {}).get("enabled") or (params or {}).get("status") or "").strip() or None
        if status in {"true", "1"}:
            status = "active"
        elif status in {"false", "0"}:
            status = "paused"
        limit = int((params or {}).get("limit") or 50)
        offset = int((params or {}).get("offset") or 0)
        rows = self.store.scheduled_job_list(
            tenant_id=tenant_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        items = [self._job_to_gateway_item(self.store.scheduled_job_to_dict(r)) for r in rows]
        return {"items": items, "total": len(items)}

    def add(self, params: dict[str, Any]) -> dict[str, Any]:
        p = dict(params or {})
        tenant_id = str(p.get("tenantId") or p.get("tenant_id") or "default").strip()
        name = str(p.get("name") or p.get("schedule") or "cron job").strip()
        schedule = str(p.get("schedule") or p.get("schedule_expr") or "").strip()
        schedule_kind = normalize_schedule_kind(p.get("schedule_kind") or p.get("scheduleKind") or "cron")
        prompt = str(p.get("prompt") or p.get("prompt_text") or p.get("text") or name).strip()
        job = self.store.scheduled_job_create(
            tenant_id=tenant_id,
            name=name,
            prompt_text=prompt,
            schedule_kind=schedule_kind,
            schedule_expr=schedule,
            timezone_name=str(p.get("timezone") or "Asia/Shanghai"),
            description=str(p.get("description") or ""),
            interaction_mode=str(p.get("interaction_mode") or "expert"),
            specialist=str(p.get("specialist") or "generalist"),
            lang=str(p.get("lang") or "zh"),
            delivery=p.get("delivery") if isinstance(p.get("delivery"), dict) else {},
            source="gateway",
        )
        return self._job_to_gateway_item(self.store.scheduled_job_to_dict(job))

    def update(self, job_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        p = dict(patch or {})
        tenant_id = str(p.pop("tenantId", None) or p.pop("tenant_id", None) or "default").strip()
        mapped: dict[str, Any] = {}
        for src, dst in (
            ("name", "name"),
            ("schedule", "schedule_expr"),
            ("schedule_kind", "schedule_kind"),
            ("prompt", "prompt_text"),
            ("prompt_text", "prompt_text"),
            ("timezone", "timezone"),
            ("interaction_mode", "interaction_mode"),
            ("specialist", "specialist"),
            ("lang", "lang"),
            ("delivery", "delivery"),
            ("enabled", "status"),
        ):
            if src in p:
                mapped[dst] = p[src]
        if "enabled" in mapped:
            mapped["status"] = "active" if bool(mapped.pop("enabled")) else "paused"
        job = self.store.scheduled_job_update(tenant_id=tenant_id, job_id=str(job_id), patch=mapped)
        if not job:
            return {"id": job_id, "ok": False}
        return self._job_to_gateway_item(self.store.scheduled_job_to_dict(job))

    def remove(self, job_id: str) -> dict[str, Any]:
        rows = self.store.scheduled_job_list(tenant_id="default", limit=500)
        for row in rows:
            if str(row.id) == str(job_id):
                self.store.scheduled_job_delete(tenant_id=row.tenant_id, job_id=str(job_id))
                return {"removed": True, "id": job_id}
        self.store.scheduled_job_delete(tenant_id="default", job_id=str(job_id))
        return {"removed": True, "id": job_id}

    def enqueueRun(self, job_id: str, mode: str = "force") -> dict[str, Any]:
        rows = self.store.scheduled_job_list(tenant_id="default", limit=500)
        tenant_id = "default"
        for row in rows:
            if str(row.id) == str(job_id):
                tenant_id = str(row.tenant_id)
                break
        out = run_scheduled_job_now(self.store, tenant_id=tenant_id, job_id=str(job_id))
        return {"ok": bool(out.get("ok")), "ran": bool(out.get("ok")), "jobId": job_id, "mode": mode, **out}

    def listRuns(self, params: dict[str, Any]) -> dict[str, Any]:
        p = dict(params or {})
        job_id = str(p.get("jobId") or p.get("id") or "").strip()
        tenant_id = str(p.get("tenantId") or p.get("tenant_id") or "default").strip()
        limit = int(p.get("limit") or 50)
        if not job_id:
            return {"items": [], "total": 0}
        rows = self.store.scheduled_job_run_list(job_id=job_id, tenant_id=tenant_id, limit=limit)
        items = [self.store.scheduled_job_run_to_dict(r) for r in rows]
        return {"items": items, "total": len(items), "jobId": job_id}

    def _job_to_gateway_item(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "name": row.get("name"),
            "schedule": row.get("schedule_expr"),
            "schedule_kind": row.get("schedule_kind"),
            "enabled": str(row.get("status") or "") == "active",
            "prompt": row.get("prompt_text"),
            "timezone": row.get("timezone"),
            "nextRunAt": row.get("next_run_at"),
            "lastRunAt": row.get("last_run_at"),
            "specialist": row.get("specialist"),
            "interaction_mode": row.get("interaction_mode"),
            "delivery": row.get("delivery"),
        }


def build_default_delivery(*, store: Any, tenant_id: str, whatsapp_chat_id: str = "") -> dict[str, Any]:
    import os

    delivery: dict[str, Any] = {
        "whatsapp": {
            "enabled": bool(str(whatsapp_chat_id or "").strip()),
            "target_type": "group" if str(whatsapp_chat_id or "").endswith("@g.us") else "direct",
            "chat_id": str(whatsapp_chat_id or ""),
            "account_id": str(os.getenv("AIA_WHATSAPP_ACCOUNT_ID") or "wa-default"),
        },
        "weixin": {"enabled": True, "fixed": True},
    }
    if not delivery["whatsapp"]["enabled"]:
        delivery["whatsapp"]["target_type"] = "none"
    binding = resolve_weixin_binding(store, tenant_id=tenant_id)
    if binding:
        ext = str(binding.get("external_user_id") or "")
        delivery["weixin"]["external_user_id"] = ext
        delivery["weixin"]["external_chat_id"] = str(binding.get("external_chat_id") or ext)
        delivery["weixin"]["account_id"] = str(binding.get("account_id") or "weixin-default")
    return delivery


def build_delivery_for_session(
    store: Any,
    *,
    tenant_id: str,
    session_id: str = "",
    whatsapp_chat_id: str = "",
) -> dict[str, Any]:
    """Pick delivery targets from the chat session that created the job (WhatsApp vs WeChat)."""
    import os

    tid = str(tenant_id or "").strip()
    sid = str(session_id or "").strip()
    explicit_wa = str(whatsapp_chat_id or "").strip()
    lookup = getattr(store, "lookup_channel_session_by_session_id", None)
    if sid and callable(lookup):
        ctx = lookup(tenant_id=tid, session_id=sid)
        if isinstance(ctx, dict):
            ch = str(ctx.get("channel") or "").strip().lower()
            chat_id = str(ctx.get("external_chat_id") or "").strip()
            acct = str(ctx.get("account_id") or "").strip()
            if ch == "whatsapp" and chat_id:
                return {
                    "whatsapp": {
                        "enabled": True,
                        "target_type": "group" if chat_id.endswith("@g.us") else "direct",
                        "chat_id": chat_id,
                        "account_id": acct or str(os.getenv("AIA_WHATSAPP_ACCOUNT_ID") or "wa-default"),
                    },
                    "weixin": {"enabled": False, "fixed": False},
                }
            if ch in {"weixin", "wechat"}:
                delivery = build_default_delivery(store=store, tenant_id=tid, whatsapp_chat_id="")
                wa = delivery.get("whatsapp") if isinstance(delivery.get("whatsapp"), dict) else {}
                delivery["whatsapp"] = {
                    **wa,
                    "enabled": False,
                    "target_type": "none",
                    "chat_id": "",
                }
                return delivery
    return build_default_delivery(store=store, tenant_id=tid, whatsapp_chat_id=explicit_wa)


__all__ = ["CronService", "build_default_delivery", "build_delivery_for_session", "compute_next_run_at"]
