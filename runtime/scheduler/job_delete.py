from __future__ import annotations

import json
from typing import Any


def _delivery_dict(job: Any) -> dict[str, Any]:
    raw = getattr(job, "delivery_json", None)
    if isinstance(job, dict):
        if isinstance(job.get("delivery"), dict):
            return dict(job.get("delivery") or {})
        raw = job.get("delivery_json")
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def creator_from_delivery(delivery: dict[str, Any] | None) -> dict[str, str]:
    raw = (delivery or {}).get("creator") if isinstance(delivery, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {
        "user_id": str(raw.get("user_id") or "").strip(),
        "external_user_id": str(raw.get("external_user_id") or "").strip(),
        "push_name": str(raw.get("push_name") or "").strip(),
        "session_id": str(raw.get("session_id") or "").strip(),
    }


def merge_delivery_creator(
    delivery: dict[str, Any] | None,
    *,
    user_id: str = "",
    external_user_id: str = "",
    push_name: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    out = dict(delivery or {})
    creator = {
        "user_id": str(user_id or "").strip(),
        "external_user_id": str(external_user_id or "").strip(),
        "push_name": str(push_name or "").strip(),
        "session_id": str(session_id or "").strip(),
    }
    if any(creator.values()):
        out["creator"] = creator
    return out


def job_is_foreign(
    job: Any,
    *,
    actor_user_id: str = "",
    actor_external_user_id: str = "",
) -> bool:
    """True when the actor is clearly not the creator (best-effort for group chats)."""
    delivery = _delivery_dict(job)
    creator = creator_from_delivery(delivery)
    actor_uid = str(actor_user_id or "").strip()
    actor_ext = str(actor_external_user_id or "").strip().lower()
    creator_uid = str(creator.get("user_id") or getattr(job, "created_by_user_id", "") or "").strip()
    if isinstance(job, dict) and not creator_uid:
        creator_uid = str(job.get("created_by_user_id") or "").strip()
    creator_ext = str(creator.get("external_user_id") or "").strip().lower()

    if actor_ext and creator_ext and actor_ext != creator_ext:
        return True
    if actor_uid and creator_uid and actor_uid != creator_uid:
        # Only treat as foreign when we also lack matching external ids
        # (same account owner may create many channel jobs).
        if creator_ext or actor_ext:
            if creator_ext and actor_ext:
                return actor_ext != creator_ext
            # external known on one side only — prefer not to block
            return False
        return True
    return False


def resolve_scheduled_jobs_by_id(
    store: Any,
    *,
    tenant_id: str,
    job_id: str,
    limit: int = 200,
) -> list[Any]:
    jid = str(job_id or "").strip()
    if not jid:
        return []
    exact = store.scheduled_job_get(job_id=jid, tenant_id=tenant_id)
    if exact is not None:
        return [exact]
    rows = store.scheduled_job_list(tenant_id=tenant_id, status=None, limit=max(1, min(int(limit), 500)))
    return [r for r in rows if str(getattr(r, "id", "") or "").startswith(jid)]


def job_delete_preview(job: Any) -> dict[str, Any]:
    delivery = _delivery_dict(job)
    creator = creator_from_delivery(delivery)
    recipe: dict[str, Any] = {}
    try:
        raw = getattr(job, "recipe_json", None)
        if isinstance(job, dict):
            if isinstance(job.get("recipe"), dict):
                recipe = dict(job.get("recipe") or {})
            else:
                raw = job.get("recipe_json")
        if not recipe and raw:
            parsed = json.loads(str(raw or "{}"))
            if isinstance(parsed, dict):
                recipe = parsed
    except Exception:
        recipe = {}
    goal = str((recipe or {}).get("goal") or getattr(job, "prompt_text", "") or "").strip()
    if isinstance(job, dict) and not goal:
        goal = str(job.get("prompt_text") or "").strip()
    return {
        "id": str(getattr(job, "id", None) or (job.get("id") if isinstance(job, dict) else "") or ""),
        "name": str(getattr(job, "name", None) or (job.get("name") if isinstance(job, dict) else "") or ""),
        "status": str(getattr(job, "status", None) or (job.get("status") if isinstance(job, dict) else "") or ""),
        "schedule_kind": str(
            getattr(job, "schedule_kind", None) or (job.get("schedule_kind") if isinstance(job, dict) else "") or ""
        ),
        "schedule_expr": str(
            getattr(job, "schedule_expr", None) or (job.get("schedule_expr") if isinstance(job, dict) else "") or ""
        ),
        "prompt_text": str(
            getattr(job, "prompt_text", None) or (job.get("prompt_text") if isinstance(job, dict) else "") or ""
        ),
        "goal": goal,
        "created_by_user_id": str(
            getattr(job, "created_by_user_id", None)
            or (job.get("created_by_user_id") if isinstance(job, dict) else "")
            or ""
        ),
        "creator": creator,
        "next_run_at": str(
            getattr(job, "next_run_at", None) or (job.get("next_run_at") if isinstance(job, dict) else "") or ""
        )
        or None,
    }


def job_delete_preview_markdown(preview: dict[str, Any], *, foreign: bool = False, lang: str = "zh") -> str:
    creator = preview.get("creator") if isinstance(preview.get("creator"), dict) else {}
    creator_label = str(creator.get("push_name") or "").strip()
    if not creator_label:
        creator_label = str(creator.get("external_user_id") or preview.get("created_by_user_id") or "").strip() or "（未知）"
    is_en = str(lang or "").lower().startswith("en")
    if is_en:
        lines = [
            "## Scheduled job delete preview (confirm required)",
            f"- **Id**: `{preview.get('id')}`",
            f"- **Name**: {preview.get('name') or '(untitled)'}",
            f"- **Schedule**: `{preview.get('schedule_kind')}` `{preview.get('schedule_expr')}`",
            f"- **Status**: {preview.get('status')}",
            f"- **Goal / prompt**: {preview.get('goal') or preview.get('prompt_text') or '(empty)'}",
            f"- **Created by**: {creator_label}",
        ]
        if foreign:
            lines.append("- **Warning**: This job appears to be created by someone else.")
        lines.append("")
        lines.append("Reply **confirm delete** with this id, then call schedule_delete with confirmed=true.")
        if foreign:
            lines.append("Also set confirm_foreign=true after the owner explicitly agrees.")
        return "\n".join(lines)
    lines = [
        "## 删除定时任务预览（需确认）",
        f"- **Id**：`{preview.get('id')}`",
        f"- **名称**：{preview.get('name') or '（未命名）'}",
        f"- **时间**：`{preview.get('schedule_kind')}` `{preview.get('schedule_expr')}`",
        f"- **状态**：{preview.get('status')}",
        f"- **目标/内容**：{preview.get('goal') or preview.get('prompt_text') or '（空）'}",
        f"- **创建者**：{creator_label}",
    ]
    if foreign:
        lines.append("- **注意**：该任务看起来是**其他人**创建的。")
    lines.append("")
    lines.append("请回复**确认删除**并带上该 id；确认后调用 `schedule_delete` 且 `confirmed=true`。")
    if foreign:
        lines.append("若删除他人任务，还需用户明确同意，并设置 `confirm_foreign=true`。")
    return "\n".join(lines)


__all__ = [
    "creator_from_delivery",
    "job_delete_preview",
    "job_delete_preview_markdown",
    "job_is_foreign",
    "merge_delivery_creator",
    "resolve_scheduled_jobs_by_id",
]
