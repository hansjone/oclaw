from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from runtime.scheduler.cron_service import build_delivery_for_session
from runtime.scheduler.expressions import normalize_schedule_kind
from runtime.scheduler.job_delete import (
    job_delete_preview,
    job_delete_preview_markdown,
    job_is_foreign,
    merge_delivery_creator,
    resolve_scheduled_jobs_by_id,
)
from runtime.scheduler.recipe import (
    looks_like_complex_schedule_prompt,
    normalize_recipe,
    parse_recipe_arg,
    preview_markdown,
    prompt_summary_from_recipe,
    recipe_has_playbook,
    recipe_missing_fields,
)
from runtime.scheduler.service import run_scheduled_job_now
from runtime.scheduler.system_timezone import default_system_timezone
from runtime.scheduler.whatsapp_mentions import (
    finalize_whatsapp_scheduled_delivery,
    merge_whatsapp_mention_jids,
    merge_whatsapp_mention_names,
)
from runtime.tools.base import ToolSpec
from runtime.tools.context_inject import enrich_tool_arguments
from runtime.types import normalize_interaction_mode, normalize_requested_specialist
from svc.persistence.assistant_store import get_assistant_store


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


def _scoped_args(store: Any, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    return enrich_tool_arguments(
        store=store,
        session_id=str(args.get("session_id") or ""),
        tool_name=tool_name,
        arguments=args,
    )


_RECIPE_PARAM = {
    "type": "object",
    "description": (
        "Self-contained workflow recipe (playbook). Required for complex/multi-step jobs. "
        "Must be understandable WITHOUT prior chat context: no '继续刚才/按上面'; "
        "put concrete paths, commands, time windows, and params in goal/steps/inputs.constants. "
        "Fields: goal, steps (>=2), success_criteria, optional constraints/inputs/output/source."
    ),
    "properties": {
        "version": {"type": "integer"},
        "goal": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "success_criteria": {"type": "array", "items": {"type": "string"}},
        "inputs": {"type": "object"},
        "output": {"type": "object"},
        "source": {"type": "object"},
    },
}


def schedule_propose_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            store = get_assistant_store()
            args = _scoped_args(store, "schedule_propose", args)
            name = str(args.get("name") or "").strip() or "Scheduled workflow"
            schedule_kind = normalize_schedule_kind(str(args.get("schedule_kind") or "cron"))
            schedule_expr = _require(str(args.get("schedule_expr") or ""), "schedule_expr")
            timezone_name = str(args.get("timezone") or default_system_timezone()).strip() or default_system_timezone()
            lang = str(args.get("lang") or "zh")
            session_id = str(args.get("session_id") or "").strip()
            recipe = normalize_recipe(parse_recipe_arg(args.get("recipe")))
            if session_id and not str((recipe.get("source") or {}).get("session_id") or "").strip():
                recipe["source"]["session_id"] = session_id
            if not str((recipe.get("source") or {}).get("compiled_at") or "").strip():
                recipe["source"]["compiled_at"] = datetime.now(timezone.utc).isoformat()

            missing = recipe_missing_fields(recipe)
            if missing:
                return {
                    "ok": False,
                    "error": "recipe_incomplete",
                    "missing_fields": missing,
                    "hint": (
                        "Fill goal, at least 2 steps, and success_criteria from the recent conversation, "
                        "then call schedule_propose again. Do not create the job yet."
                    ),
                    "recipe": recipe,
                }

            preview = preview_markdown(
                name=name,
                schedule_kind=schedule_kind,
                schedule_expr=schedule_expr,
                timezone_name=timezone_name,
                recipe=recipe,
                lang=lang,
            )
            return {
                "ok": True,
                "draft": True,
                "name": name,
                "schedule_kind": schedule_kind,
                "schedule_expr": schedule_expr,
                "timezone": timezone_name,
                "recipe": recipe,
                "prompt_text": prompt_summary_from_recipe(recipe, fallback=name),
                "preview_markdown": preview,
                "next_step": (
                    "Show preview_markdown to the user. After they confirm (or request edits), "
                    "call schedule_create with the same recipe and schedule fields."
                ),
            }
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="schedule_propose",
        description=(
            "Draft a scheduled workflow recipe WITHOUT creating the job. "
            "Use when the user wants to schedule a multi-step task they just guided "
            "(e.g. '做成定时/每周跑刚才那套'). "
            "CRITICAL: the recipe must be self-contained — at fire time there is no prior chat; "
            "a new LLM must understand the task from recipe alone (no '继续刚才', embed paths/params in steps/constants). "
            "Compile goal/steps(>=2)/success_criteria/constraints from the conversation into `recipe`, "
            "then show preview_markdown and wait for confirmation before schedule_create."
        ),
        parameters={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string", "description": "Auto-filled from session; do not guess."},
                "owner_user_id": {"type": "string", "description": "Auto-filled from session."},
                "session_id": {"type": "string", "description": "Auto-filled from session."},
                "name": {"type": "string"},
                "recipe": _RECIPE_PARAM,
                "schedule_kind": {"type": "string", "enum": ["cron", "once", "interval"]},
                "schedule_expr": {"type": "string"},
                "timezone": {"type": "string"},
                "lang": {"type": "string"},
            },
            "required": ["recipe", "schedule_kind", "schedule_expr"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "schedule"}),
    )


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
            prompt_text = str(args.get("prompt_text") or "").strip()
            recipe_raw = parse_recipe_arg(args.get("recipe"))
            recipe = normalize_recipe(recipe_raw) if recipe_raw is not None else {}
            if recipe_has_playbook(recipe):
                prompt_text = prompt_summary_from_recipe(recipe, fallback=prompt_text or name)
            if not prompt_text:
                raise ValueError("prompt_text is required")

            needs_recipe = looks_like_complex_schedule_prompt(prompt_text, recipe=recipe)
            if needs_recipe and not recipe_has_playbook(recipe):
                missing = recipe_missing_fields(recipe) or ["goal", "steps", "success_criteria"]
                return {
                    "ok": False,
                    "error": "recipe_required",
                    "missing_fields": missing,
                    "hint": (
                        "This looks like a complex/multi-step job. Call schedule_propose first, "
                        "show the draft to the user, then schedule_create with a full recipe "
                        "(goal + >=2 steps + success_criteria). Do not store vague prompts like "
                        "'继续刚才那个'."
                    ),
                }
            if recipe and not recipe_has_playbook(recipe) and recipe_missing_fields(recipe):
                # Explicit but incomplete recipe → reject rather than silently drop.
                return {
                    "ok": False,
                    "error": "recipe_incomplete",
                    "missing_fields": recipe_missing_fields(recipe),
                    "hint": "Complete the recipe or omit it for a simple reminder.",
                }

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
            delivery = merge_whatsapp_mention_jids(
                delivery,
                args.get("whatsapp_mention_jids") if args.get("whatsapp_mention_jids") is not None else None,
            )
            delivery = merge_whatsapp_mention_names(
                delivery,
                args.get("whatsapp_mention_names") if args.get("whatsapp_mention_names") is not None else None,
            )
            session_id = str(args.get("session_id") or "").strip() or None
            delivery = merge_delivery_creator(
                delivery,
                user_id=owner_user_id,
                external_user_id=str(args.get("creator_external_user_id") or "").strip(),
                push_name=str(args.get("creator_push_name") or "").strip(),
                session_id=str(session_id or ""),
            )
            delivery = finalize_whatsapp_scheduled_delivery(
                delivery,
                creator_external_user_id=str(args.get("creator_external_user_id") or "").strip(),
                creator_push_name=str(args.get("creator_push_name") or "").strip(),
                bot_jid=str(args.get("whatsapp_bot_jid") or "").strip(),
                bot_lid=str(args.get("whatsapp_bot_lid") or "").strip(),
            )
            interaction_mode = normalize_interaction_mode(
                str(args.get("interaction_mode") or "expert")
            )
            specialist = normalize_requested_specialist(
                str(args.get("specialist") or args.get("selected_specialist") or "generalist")
            )
            if recipe_has_playbook(recipe):
                if session_id and not str((recipe.get("source") or {}).get("session_id") or "").strip():
                    recipe["source"]["session_id"] = session_id
                if not str((recipe.get("source") or {}).get("compiled_at") or "").strip():
                    recipe["source"]["compiled_at"] = datetime.now(timezone.utc).isoformat()
            else:
                recipe = {}

            row = store.scheduled_job_create(
                tenant_id=tenant_id,
                name=name,
                prompt_text=prompt_text,
                schedule_kind=schedule_kind,
                schedule_expr=schedule_expr,
                timezone_name=str(args.get("timezone") or default_system_timezone()),
                description=str(args.get("description") or ""),
                interaction_mode=interaction_mode,
                specialist=specialist,
                lang=str(args.get("lang") or "zh"),
                delivery=delivery,
                recipe=recipe,
                source_session_id=session_id,
                created_by_user_id=owner_user_id,
                source="chat",
            )
            return {"ok": True, "job": store.scheduled_job_to_dict(row)}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="schedule_create",
        description=(
            "Create a scheduled job after the user confirmed the draft. "
            "Simple reminders may use prompt_text only. "
            "Complex / multi-step / '刚才那件事做成定时' jobs MUST include a self-contained recipe "
            "(goal + >=2 concrete steps + success_criteria; no chat-dependent phrasing); "
            "call schedule_propose and get user confirmation first. "
            "Delivery follows the current chat channel unless delivery is set explicitly."
        ),
        parameters={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string", "description": "Auto-filled from session; do not guess."},
                "owner_user_id": {"type": "string", "description": "Auto-filled from session."},
                "session_id": {"type": "string", "description": "Auto-filled from session."},
                "name": {"type": "string"},
                "prompt_text": {
                    "type": "string",
                    "description": "Short summary / reminder intent. For playbooks, prefer recipe.goal.",
                },
                "recipe": _RECIPE_PARAM,
                "schedule_kind": {"type": "string", "enum": ["cron", "once", "interval"]},
                "schedule_expr": {"type": "string"},
                "timezone": {"type": "string", "description": "IANA timezone; defaults to the host system timezone."},
                "interaction_mode": {"type": "string"},
                "specialist": {"type": "string"},
                "selected_specialist": {"type": "string"},
                "lang": {"type": "string"},
                "whatsapp_chat_id": {"type": "string"},
                "whatsapp_mention_jids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "WhatsApp JIDs to @mention on delivery (e.g. 628...@s.whatsapp.net). Stored in delivery.whatsapp.mention_jids.",
                },
                "whatsapp_mention_names": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "creator_external_user_id": {
                    "type": "string",
                    "description": "Auto-filled channel sender id for group ownership checks.",
                },
                "creator_push_name": {
                    "type": "string",
                    "description": "Auto-filled channel display name of the creator.",
                },
                "whatsapp_bot_jid": {
                    "type": "string",
                    "description": "Auto-filled bot JID for filtering self-mentions on delivery.",
                },
                "whatsapp_bot_lid": {
                    "type": "string",
                    "description": "Auto-filled bot LID for filtering self-mentions on delivery.",
                },
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
            recipe_raw = parse_recipe_arg(args.get("recipe"))
            if recipe_raw is not None:
                recipe = normalize_recipe(recipe_raw)
                if recipe_has_playbook(recipe):
                    patch["recipe"] = recipe
                    if "prompt_text" not in patch:
                        patch["prompt_text"] = prompt_summary_from_recipe(recipe)
                elif recipe_missing_fields(recipe):
                    return {
                        "ok": False,
                        "error": "recipe_incomplete",
                        "missing_fields": recipe_missing_fields(recipe),
                    }
                else:
                    patch["recipe"] = {}
            row = store.scheduled_job_update(tenant_id=tenant_id, job_id=job_id, patch=patch)
            if not row:
                return {"ok": False, "error": "job_not_found"}
            return {"ok": True, "job": store.scheduled_job_to_dict(row)}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="schedule_update",
        description="Update a scheduled job (including recipe playbook fields).",
        parameters={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},
                "job_id": {"type": "string"},
                "name": {"type": "string"},
                "prompt_text": {"type": "string"},
                "recipe": _RECIPE_PARAM,
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
            confirmed = bool(args.get("confirmed"))
            confirm_foreign = bool(args.get("confirm_foreign"))
            lang = str(args.get("lang") or "zh")
            actor_user_id = str(args.get("owner_user_id") or args.get("user_id") or "").strip()
            actor_external_user_id = str(args.get("actor_external_user_id") or "").strip()

            matches = resolve_scheduled_jobs_by_id(store, tenant_id=tenant_id, job_id=job_id)
            if not matches:
                return {"ok": False, "error": "job_not_found", "job_id": job_id}
            if len(matches) > 1:
                candidates = [job_delete_preview(j) for j in matches[:10]]
                return {
                    "ok": False,
                    "error": "ambiguous_job",
                    "candidates": candidates,
                    "hint": (
                        "Multiple jobs match this id prefix. Show candidates to the user and "
                        "retry schedule_delete with the full job id."
                    ),
                }

            job = matches[0]
            preview = job_delete_preview(job)
            foreign = job_is_foreign(
                job,
                actor_user_id=actor_user_id,
                actor_external_user_id=actor_external_user_id,
            )
            preview_md = job_delete_preview_markdown(preview, foreign=foreign, lang=lang)

            if not confirmed:
                return {
                    "ok": False,
                    "error": "confirmation_required",
                    "needs_confirm": True,
                    "foreign_job": foreign,
                    "job_id": preview["id"],
                    "preview": preview,
                    "preview_markdown": preview_md,
                    "next_step": (
                        "Show preview_markdown to the user. After they explicitly confirm deleting "
                        "THIS job, call schedule_delete again with the full job_id and confirmed=true"
                        + (", and confirm_foreign=true if foreign_job" if foreign else "")
                        + "."
                    ),
                }

            if foreign and not confirm_foreign:
                return {
                    "ok": False,
                    "error": "foreign_job_confirmation_required",
                    "needs_confirm": True,
                    "foreign_job": True,
                    "job_id": preview["id"],
                    "preview": preview,
                    "preview_markdown": preview_md,
                    "hint": (
                        "This job was created by someone else. Only delete after the user clearly "
                        "agrees, then set confirmed=true and confirm_foreign=true."
                    ),
                }

            ok = store.scheduled_job_delete(tenant_id=tenant_id, job_id=str(preview["id"]))
            if not ok:
                return {"ok": False, "error": "job_not_found", "job_id": preview["id"]}
            return {"ok": True, "job_id": preview["id"], "deleted": preview}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="schedule_delete",
        description=(
            "Soft-delete a scheduled job WITH confirmation. "
            "First call WITHOUT confirmed (or confirmed=false) to get preview_markdown; "
            "show it to the user. After explicit user confirmation, call again with "
            "confirmed=true. If foreign_job (created by someone else in a group), also set "
            "confirm_foreign=true. Never guess when multiple jobs match — resolve ambiguity first. "
            "Prefer pausing instead of deleting when the user only wants to stop temporary runs."
        ),
        parameters={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},
                "job_id": {
                    "type": "string",
                    "description": "Full job id preferred; prefix allowed only when unique.",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "Must be true to actually delete after user confirmation.",
                    "default": False,
                },
                "confirm_foreign": {
                    "type": "boolean",
                    "description": "Required when deleting a job created by someone else.",
                    "default": False,
                },
                "actor_external_user_id": {
                    "type": "string",
                    "description": "Auto-filled channel sender id for ownership checks.",
                },
                "lang": {"type": "string"},
            },
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
    "schedule_propose_tool",
    "schedule_list_tool",
    "schedule_update_tool",
    "schedule_pause_tool",
    "schedule_resume_tool",
    "schedule_delete_tool",
    "schedule_run_now_tool",
]
