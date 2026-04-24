from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from oclaw.runtime.types import StandardMessage
from oclaw.runtime.types import normalize_interaction_mode, normalize_requested_specialist
from oclaw.prompts.loader import render_runtime_prompt


@dataclass(frozen=True)
class RouterDecision:
    mode: str  # sync_direct | async_task
    reason: str
    skill_signal: str = ""
    interaction_mode: str = "comprehensive"
    requested_specialist: str = "generalist"


_ASYNC_HINTS = (
    "总结并发送",
    "总结后发送",
    "发到",
    "发送到",
    "send to",
    "summarize and send",
    "总结一下并发",
)


def _router_mode_from_store(store: Any | None) -> str:
    raw = ""
    if store is not None:
        try:
            raw = str(store.get_setting("AIA_OCLAW_ROUTER_MODE") or "").strip().lower()
        except Exception:
            raw = ""
    if not raw:
        raw = str(os.getenv("AIA_OCLAW_ROUTER_MODE", "") or "").strip().lower()
    return raw or "rule"


def _decide_rule(msg: StandardMessage, *, skill_count: int = 0) -> RouterDecision:
    text = str(msg.text or "").strip().lower()
    has_attachments = bool(msg.attachments)
    if any(h in text for h in _ASYNC_HINTS):
        return RouterDecision(mode="async_task", reason="multi_step_send_flow", skill_signal=f"skills={int(skill_count)}")
    if has_attachments and len(text) >= 120:
        return RouterDecision(mode="async_task", reason="long_with_attachments", skill_signal=f"skills={int(skill_count)}")
    return RouterDecision(mode="sync_direct", reason="default_sync", skill_signal=f"skills={int(skill_count)}")


def _parse_router_json_object(text: str) -> dict[str, Any] | None:
    t = str(text or "").strip()
    start = t.find("{")
    if start < 0:
        return None
    try:
        obj, _end = json.JSONDecoder().raw_decode(t[start:])
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _decide_llm_json(msg: StandardMessage, *, model: Any | None) -> RouterDecision | None:
    if model is None or not callable(getattr(model, "chat", None)):
        return None
    try:
        user_block = render_runtime_prompt(
            "router/decide_route.md",
            variables={
                "user_text": str(msg.text or "").strip(),
                "has_attachments": "yes" if bool(msg.attachments) else "no",
            },
            strict=True,
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a routing classifier. Output exactly one JSON object on one line: "
                    '{"mode":"sync_direct"|"async_task","reason":"..."}. No markdown, no extra text.'
                ),
            },
            {"role": "user", "content": user_block},
        ]
        resp = model.chat(messages, [], on_token=None)
        raw = str(getattr(resp, "content", "") or "")
        obj = _parse_router_json_object(raw)
        if not obj:
            return None
        mode = str(obj.get("mode") or "").strip().lower()
        reason = str(obj.get("reason") or "").strip() or "llm_router"
        if mode not in {"sync_direct", "async_task"}:
            return None
        return RouterDecision(mode=mode, reason=reason)
    except Exception:
        return None


def decide_route(msg: StandardMessage, *, store: Any | None = None, model: Any | None = None) -> RouterDecision:
    md = msg.metadata if isinstance(msg.metadata, dict) else {}
    interaction_mode = normalize_interaction_mode(md.get("interaction_mode"))
    requested_specialist = normalize_requested_specialist(md.get("selected_specialist"))
    skill_count = 0
    try:
        skill_count = int(md.get("skills_total") or 0)
    except Exception:
        skill_count = 0
    mode = _router_mode_from_store(store)
    if mode == "llm_json":
        d = _decide_llm_json(msg, model=model)
        if d is not None:
            return RouterDecision(
                mode=d.mode,
                reason=d.reason,
                skill_signal=f"skills={int(skill_count)}",
                interaction_mode=interaction_mode,
                requested_specialist=requested_specialist,
            )
    d2 = _decide_rule(msg, skill_count=skill_count)
    return RouterDecision(
        mode=d2.mode,
        reason=d2.reason,
        skill_signal=d2.skill_signal,
        interaction_mode=interaction_mode,
        requested_specialist=requested_specialist,
    )


__all__ = ["RouterDecision", "decide_route"]

