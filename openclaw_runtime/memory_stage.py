from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from oclaw.openclaw_runtime.types import OpenClawMemoryContext
from oclaw.orchestration.memory import semantic_retrieve, session_memory_digest
from oclaw.prompts.loader import render_openclaw_prompt

_SPECIALIST_FLAGS_SETTING_KEY = "AIA_CHAT_SPECIALIST_FLAGS_JSON"


def build_memory_context(
    *,
    store: Any,
    session_id: str,
    tenant_id: str,
    user_id: str,
    query_text: str,
    short_limit: int = 6,
    semantic_top_k: int = 4,
) -> OpenClawMemoryContext:
    short_term: tuple[str, ...] = ()
    semantic_hits: tuple[dict[str, Any], ...] = ()

    try:
        short = session_memory_digest(store, session_id, max_items=max(1, min(int(short_limit), 20)))
        short_term = tuple([str(x) for x in (short or []) if str(x).strip()])
    except Exception:
        short_term = ()

    t = str(tenant_id or "").strip()
    u = str(user_id or "").strip()
    q = str(query_text or "").strip()
    if t and u and q:
        try:
            hits = semantic_retrieve(
                store,
                query=q,
                tenant_id=t,
                user_id=u,
                session_id=session_id,
                top_k=max(1, min(int(semantic_top_k), 12)),
            )
            semantic_hits = tuple([h for h in (hits or []) if isinstance(h, dict)])
        except Exception:
            semantic_hits = ()

    return OpenClawMemoryContext(short_term=short_term, semantic_hits=semantic_hits)


def render_memory_context_block(ctx: OpenClawMemoryContext) -> str:
    if not ctx.enabled:
        return ""
    short_lines: list[str] = []
    sem_lines: list[str] = []
    if ctx.short_term:
        for i, x in enumerate(ctx.short_term, start=1):
            short_lines.append(f"{i}. {x}")
    if ctx.semantic_hits:
        for i, h in enumerate(ctx.semantic_hits, start=1):
            content = str(h.get("content") or "").strip()
            score = h.get("score")
            score_text = ""
            try:
                score_text = f" score={float(score):.4f}" if score is not None else ""
            except Exception:
                score_text = ""
            sem_lines.append(f"{i}.{score_text} {content[:500]}")
    return render_openclaw_prompt(
        "runtime/memory_context_block.md",
        variables={
            "short_term_block": "\n".join(short_lines).strip(),
            "semantic_hits_block": "\n".join(sem_lines).strip(),
        },
        strict=True,
    )


def assemble_memory_context(
    *,
    store: Any,
    session_id: str,
    tenant_id: str,
    user_id: str,
    query_text: str,
) -> OpenClawMemoryContext:
    return build_memory_context(
        store=store,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        query_text=query_text,
    )


def ingest_after_turn(
    *,
    store: Any,
    session_id: str,
    tenant_id: str,
    user_id: str,
    user_text: str,
    assistant_text: str,
) -> None:
    # MVP lifecycle hook: current runtime already persists messages in chat_message;
    # long-term memory write can be layered here later without changing orchestrator contracts.
    _ = (store, session_id, tenant_id, user_id, user_text, assistant_text)


def compact_memory_context(
    *,
    store: Any,
    session_id: str,
    tenant_id: str,
    user_id: str,
) -> OpenClawMemoryContext:
    # MVP compaction path: return fresh assembled short+semantic context.
    return assemble_memory_context(
        store=store,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        query_text="",
    )


def after_turn_memory(
    *,
    store: Any,
    session_id: str,
    tenant_id: str,
    user_id: str,
    user_text: str,
    assistant_text: str,
    turn_uuid: str = "",
) -> None:
    ingest_after_turn(
        store=store,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        user_text=user_text,
        assistant_text=assistant_text,
    )
    try:
        from oclaw.orchestration.memory import maybe_write_turn_memory
        from oclaw.platform.persistence.sqlite_store import SqliteStore

        if isinstance(store, SqliteStore):
            maybe_write_turn_memory(
                store,
                tenant_id=str(tenant_id or ""),
                user_id=str(user_id or ""),
                session_id=str(session_id or ""),
                user_text=str(user_text or ""),
                assistant_text=str(assistant_text or ""),
            )
    except Exception:
        pass
    try:
        raw_flags = str(store.get_setting(_SPECIALIST_FLAGS_SETTING_KEY) or "").strip() if hasattr(store, "get_setting") else ""
        if raw_flags:
            obj = json.loads(raw_flags)
            if isinstance(obj, dict) and not bool(obj.get("memory_curator", True)):
                return
    except Exception:
        pass
    try:
        cfg_path = Path(__file__).resolve().parents[2] / "oclaw" / "oclaw.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
        plugins = cfg.get("plugins") if isinstance(cfg, dict) else {}
        entries = plugins.get("entries") if isinstance(plugins, dict) else {}
        wiki_entry = entries.get("memory-wiki") if isinstance(entries, dict) else {}
        auto = wiki_entry.get("auto") if isinstance(wiki_entry, dict) else {}
        if bool(auto.get("enabled", False)):
            payload = {
                "kind": "captureAfterTurn",
                "session_id": str(session_id or ""),
                "tenant_id": str(tenant_id or ""),
                "user_id": str(user_id or ""),
                "turn_uuid": str(turn_uuid or ""),
                "user_text": str(user_text or "")[:8000],
                "assistant_text": str(assistant_text or "")[:12000],
            }
            if hasattr(store, "openclaw_task_create"):
                store.openclaw_task_create(
                    tenant_id=str(tenant_id or "default"),
                    session_id=str(session_id or ""),
                    task_type="wiki_capture",
                    payload=payload,
                )
    except Exception:
        pass


__all__ = [
    "build_memory_context",
    "render_memory_context_block",
    "assemble_memory_context",
    "ingest_after_turn",
    "compact_memory_context",
    "after_turn_memory",
]

