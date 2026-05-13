from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

from svc.persistence.sqlite_store import SqliteStore
from svc.embeddings.embedding_client import build_default_embedding_client
from runtime.orchestration.vector_store import (
    MemoryVectorItem,
    read_vector_memory_runtime,
    semantic_search,
    build_vector_store,
)


def _chunk_id(source: str, text: str) -> str:
    raw = f"{source}\n{text}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()


def upsert_knowledge_chunks(store: SqliteStore, source: str, chunks: list[str]) -> int:
    inserted = 0
    for chunk in chunks:
        text = (chunk or "").strip()
        if not text:
            continue
        store.upsert_knowledge_chunk(
            chunk_id=_chunk_id(source, text),
            source=source,
            content=text,
            metadata={"source": source},
        )
        inserted += 1
    return inserted


def retrieve_context(store: SqliteStore, query: str, *, limit: int = 3) -> list[dict[str, Any]]:
    mode = (store.get_setting("rag_mode") or "").strip().lower()
    if not mode:
        import os

        mode = (os.getenv("AIA_RAG_MODE") or "").strip().lower()
    if mode == "vector":
        try:
            return retrieve_context_vector(store, query, limit=limit)
        except Exception:
            return store.search_knowledge(query=query, limit=limit)
    return store.search_knowledge(query=query, limit=limit)


def _dot(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    return float(sum(float(a[i]) * float(b[i]) for i in range(n)))


def _norm(a: list[float]) -> float:
    return float(sum(float(x) * float(x) for x in a)) ** 0.5


def _cosine(a: list[float], b: list[float]) -> float:
    na = _norm(a)
    nb = _norm(b)
    if na <= 1e-9 or nb <= 1e-9:
        return 0.0
    return _dot(a, b) / (na * nb)


def retrieve_context_vector(store: SqliteStore, query: str, *, limit: int = 3) -> list[dict[str, Any]]:
    token = (query or "").strip()
    if not token:
        return []
    client = build_default_embedding_client()
    q = client.embed(token)
    emb_rows = store.list_knowledge_embeddings(model=q.model, limit=8000)
    scored: list[tuple[float, str]] = []
    for r in emb_rows:
        vec = r.get("vector")
        if not isinstance(vec, list):
            continue
        try:
            score = _cosine(q.vector, [float(x) for x in vec])
        except Exception:
            continue
        scored.append((score, str(r.get("chunk_id") or "")))
    scored.sort(key=lambda x: x[0], reverse=True)
    top_scored = [(float(s), cid) for s, cid in scored[: max(1, int(limit))] if cid]
    top_ids = [cid for _s, cid in top_scored]
    if not top_ids:
        return []
    chunks = store.get_knowledge_chunks(chunk_ids=top_ids)
    # keep order stable by score
    by_id = {c.get("chunk_id"): c for c in chunks}
    out: list[dict[str, Any]] = []
    score_by_id = {cid: float(s) for s, cid in top_scored}
    for cid in top_ids:
        c = by_id.get(cid)
        if c:
            out.append(
                {
                    "source": str(c.get("source") or "kb"),
                    "content": c.get("content") or "",
                    "metadata": c.get("metadata") if isinstance(c.get("metadata"), dict) else {},
                    "updated_at": c.get("updated_at") or "",
                    "score": float(score_by_id.get(cid) or 0.0),
                    "chunk_id": str(cid),
                }
            )
    return out


def session_memory_digest(store: SqliteStore, session_id: str, *, max_items: int = 6) -> list[str]:
    msgs = store.get_messages(session_id=session_id, limit=max_items)
    out: list[str] = []
    for m in msgs:
        content = (m.content or "").strip()
        if content:
            out.append(f"{m.role}: {content[:180]}")
    return out[-max_items:]


def semantic_retrieve(
    store: SqliteStore,
    *,
    query: str,
    tenant_id: str,
    user_id: str,
    session_id: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    runtime = read_vector_memory_runtime(store)
    if not runtime.enabled:
        return []
    token = (query or "").strip()
    if not token or not tenant_id or not user_id:
        return []
    client = build_default_embedding_client()
    try:
        hits = semantic_search(
            store=store,
            embedder=client,
            query=token,
            tenant_id=tenant_id,
            user_id=user_id,
            top_k=max(1, min(int(top_k), 20)),
        )
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for h in hits:
        try:
            store.add_memory_hit_log(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                memory_id=h.memory_id,
                query_text=token,
                score=float(h.score),
                source=str(h.source or "vector"),
            )
        except Exception:
            pass
        out.append(
            {
                "memory_id": h.memory_id,
                "score": float(h.score),
                "source": str(h.source or "vector"),
                "content": h.content,
                "tenant_id": h.tenant_id,
                "user_id": h.user_id,
                "session_id": h.session_id,
                "memory_type": h.memory_type,
                "confidence": float(h.confidence),
                "created_at": h.created_at,
                "metadata": h.metadata or {},
            }
        )
    return out


def _normalize_memory_text(text: str) -> str:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    return s[:600]


def maybe_write_turn_memory(
    store: SqliteStore,
    *,
    tenant_id: str,
    user_id: str,
    session_id: str,
    user_text: str,
    assistant_text: str,
) -> dict[str, Any]:
    runtime = read_vector_memory_runtime(store)
    if not runtime.writer_enabled:
        return {"ok": True, "written": 0, "reason": "writer_disabled"}
    user_norm = _normalize_memory_text(user_text)
    assistant_norm = _normalize_memory_text(assistant_text)
    if not user_norm or not assistant_norm:
        return {"ok": True, "written": 0, "reason": "empty_turn"}
    # High-value heuristic in v1: preference/fact/decision-like statements.
    low = user_norm.lower()
    is_high_value = any(
        key in low
        for key in ("我喜欢", "偏好", "记住", "以后", "每次", "always", "prefer", "my name", "习惯", "决定")
    ) or len(user_norm) >= 24
    if not is_high_value:
        return {"ok": True, "written": 0, "reason": "below_value_threshold"}
    confidence = 0.8 if len(user_norm) >= 24 else 0.7
    if confidence < runtime.write_min_confidence:
        return {"ok": True, "written": 0, "reason": "below_confidence_threshold"}

    dedupe_key = hashlib.sha1(f"{tenant_id}:{user_id}:{user_norm}".encode("utf-8", errors="ignore")).hexdigest()
    existing = store.list_memory_items(tenant_id=tenant_id, user_id=user_id, limit=100)
    if any(str(x.get("metadata", {}).get("dedupe_key") or "") == dedupe_key for x in existing):
        return {"ok": True, "written": 0, "reason": "deduped"}

    content = f"User: {user_norm}\nAssistant: {assistant_norm[:320]}"
    now = store.get_setting("memory_now_override") or None
    # TTL (best-effort): allow expiring episodic memories by default to reduce long-term risk.
    expires_at: str | None = None
    try:
        import os
        from datetime import datetime, timedelta, timezone

        days_raw = (
            store.get_setting("AIA_MEMORY_EPISODIC_TTL_DAYS")
            or store.get_setting("MEMORY_EPISODIC_TTL_DAYS")
            or os.getenv("AIA_MEMORY_EPISODIC_TTL_DAYS")
            or os.getenv("MEMORY_EPISODIC_TTL_DAYS")
            or "90"
        ).strip()
        days = int(float(days_raw))
        if days > 0:
            expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    except Exception:
        expires_at = None
    item = MemoryVectorItem(
        memory_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        memory_type="episodic_memory",
        content=content,
        confidence=confidence,
        created_at=now or "",
        updated_at=now or "",
        expires_at=expires_at,
        metadata={"dedupe_key": dedupe_key, "write_policy": "high_value_v1"},
    )
    client = build_default_embedding_client()
    emb = client.embed(content)
    store.upsert_memory_item(
        memory_id=item.memory_id,
        tenant_id=item.tenant_id,
        user_id=item.user_id,
        session_id=item.session_id,
        memory_type=item.memory_type,
        content=item.content,
        confidence=item.confidence,
        source="memory:write_pipeline",
        metadata=item.metadata or {},
        created_at=item.created_at or None,
        updated_at=item.updated_at or None,
        expires_at=item.expires_at,
    )
    try:
        vs = build_vector_store(store)
        vs.upsert(item, emb.vector, model=emb.model)
    except Exception:
        # Keep sqlite metadata even if vector backend fails.
        store.upsert_memory_vector(memory_id=item.memory_id, model=emb.model, vector=emb.vector)
    return {"ok": True, "written": 1, "memory_id": item.memory_id, "confidence": confidence}
