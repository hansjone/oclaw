from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from oclaw.platform.embeddings.embedding_client import EmbeddingClient
from oclaw.platform.persistence.sqlite_store import SqliteStore


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"1", "true", "yes", "y", "on"}:
            return True
        if s in {"0", "false", "no", "n", "off"}:
            return False
    return default


@dataclass(frozen=True)
class MemoryVectorItem:
    memory_id: str
    tenant_id: str
    user_id: str
    session_id: str
    memory_type: str
    content: str
    confidence: float
    created_at: str
    updated_at: str
    expires_at: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class MemoryVectorHit:
    memory_id: str
    score: float
    source: str
    content: str
    tenant_id: str
    user_id: str
    session_id: str
    memory_type: str
    confidence: float
    created_at: str
    metadata: dict[str, Any] | None = None


class VectorStore(Protocol):
    def upsert(self, item: MemoryVectorItem, vector: list[float], *, model: str) -> None: ...

    def search(
        self,
        *,
        query_vector: list[float],
        tenant_id: str,
        user_id: str,
        top_k: int,
        model: str,
    ) -> list[MemoryVectorHit]: ...


class SqliteVectorStore:
    def __init__(self, store: SqliteStore):
        self.store = store
        self.store.ensure_memory_tables()

    def upsert(self, item: MemoryVectorItem, vector: list[float], *, model: str) -> None:
        self.store.upsert_memory_item(
            memory_id=item.memory_id,
            tenant_id=item.tenant_id,
            user_id=item.user_id,
            session_id=item.session_id,
            memory_type=item.memory_type,
            content=item.content,
            confidence=float(item.confidence),
            source="vector:sqlite",
            metadata=item.metadata or {},
            created_at=item.created_at,
            updated_at=item.updated_at,
            expires_at=item.expires_at,
        )
        self.store.upsert_memory_vector(
            memory_id=item.memory_id,
            model=model,
            vector=[float(x) for x in (vector or [])],
            updated_at=item.updated_at or _utc_now_iso(),
        )

    def search(
        self,
        *,
        query_vector: list[float],
        tenant_id: str,
        user_id: str,
        top_k: int,
        model: str,
    ) -> list[MemoryVectorHit]:
        rows = self.store.search_memory_vectors(
            query_vector=query_vector,
            model=model,
            tenant_id=tenant_id,
            user_id=user_id,
            limit=top_k,
        )
        out: list[MemoryVectorHit] = []
        for row in rows:
            out.append(
                MemoryVectorHit(
                    memory_id=str(row.get("memory_id") or ""),
                    score=float(row.get("score") or 0.0),
                    source=str(row.get("source") or "vector:sqlite"),
                    content=str(row.get("content") or ""),
                    tenant_id=str(row.get("tenant_id") or ""),
                    user_id=str(row.get("user_id") or ""),
                    session_id=str(row.get("session_id") or ""),
                    memory_type=str(row.get("memory_type") or "semantic"),
                    confidence=float(row.get("confidence") or 0.0),
                    created_at=str(row.get("created_at") or ""),
                    metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
                )
            )
        return out


class ChromaVectorStore(SqliteVectorStore):
    """Best-effort adapter: delegates to SQLite if Chroma client is unavailable."""

    def __init__(self, store: SqliteStore):
        super().__init__(store)
        self._available = False
        try:
            import chromadb  # noqa: F401

            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available


class QdrantVectorStore(SqliteVectorStore):
    """Best-effort adapter: delegates to SQLite if Qdrant client is unavailable."""

    def __init__(self, store: SqliteStore):
        super().__init__(store)
        self._available = False
        try:
            import qdrant_client  # noqa: F401

            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available


@dataclass(frozen=True)
class VectorMemoryRuntime:
    enabled: bool
    backend: str
    top_k: int
    writer_enabled: bool
    write_min_confidence: float


def read_vector_memory_runtime(store: SqliteStore) -> VectorMemoryRuntime:
    def _get(name: str, default: str) -> str:
        v = store.get_setting(name)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
        return str(os.getenv(name) or default).strip()

    enabled = _parse_bool(_get("MEMORY_VECTOR_ENABLED", "0"), default=False)
    backend = (_get("MEMORY_VECTOR_BACKEND", "sqlite") or "sqlite").strip().lower()
    if backend not in {"sqlite", "chroma", "qdrant"}:
        backend = "sqlite"
    try:
        top_k = max(1, min(20, int(_get("MEMORY_VECTOR_TOPK", "5"))))
    except Exception:
        top_k = 5
    writer_enabled = _parse_bool(_get("MEMORY_WRITE_ENABLED", "0"), default=False)
    try:
        write_min_confidence = float(_get("MEMORY_WRITE_MIN_CONFIDENCE", "0.75"))
    except Exception:
        write_min_confidence = 0.75
    return VectorMemoryRuntime(
        enabled=enabled,
        backend=backend,
        top_k=top_k,
        writer_enabled=writer_enabled,
        write_min_confidence=max(0.0, min(1.0, write_min_confidence)),
    )


def build_vector_store(store: SqliteStore) -> VectorStore:
    runtime = read_vector_memory_runtime(store)
    if runtime.backend == "chroma":
        adapter = ChromaVectorStore(store)
        if adapter.available:
            return adapter
    if runtime.backend == "qdrant":
        adapter = QdrantVectorStore(store)
        if adapter.available:
            return adapter
    return SqliteVectorStore(store)


def semantic_search(
    *,
    store: SqliteStore,
    embedder: EmbeddingClient,
    query: str,
    tenant_id: str,
    user_id: str,
    top_k: int,
) -> list[MemoryVectorHit]:
    token = (query or "").strip()
    if not token or not tenant_id or not user_id:
        return []
    emb = embedder.embed(token)
    vs = build_vector_store(store)
    return vs.search(
        query_vector=emb.vector,
        tenant_id=tenant_id,
        user_id=user_id,
        top_k=max(1, int(top_k)),
        model=emb.model,
    )


def dump_hit_json(hit: MemoryVectorHit) -> str:
    return json.dumps(
        {
            "memory_id": hit.memory_id,
            "score": hit.score,
            "source": hit.source,
            "tenant_id": hit.tenant_id,
            "user_id": hit.user_id,
            "session_id": hit.session_id,
            "memory_type": hit.memory_type,
            "confidence": hit.confidence,
            "created_at": hit.created_at,
            "metadata": hit.metadata or {},
        },
        ensure_ascii=False,
    )


__all__ = [
    "MemoryVectorHit",
    "MemoryVectorItem",
    "VectorMemoryRuntime",
    "VectorStore",
    "build_vector_store",
    "dump_hit_json",
    "read_vector_memory_runtime",
    "semantic_search",
]
