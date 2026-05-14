from __future__ import annotations

import hashlib
from typing import Any

from svc.config.paths import db_path
from svc.embeddings.embedding_client import build_default_embedding_client
from svc.persistence.sqlite_store import SqliteStore
from svc.persistence.assistant_store import get_assistant_store
from runtime.tools.base import ToolSpec


def _chunk_id(source: str, text: str) -> str:
    raw = f"{source}\n{text}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()


def kb_add_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            tenant_id = str(args.get("tenant_id") or "").strip()
            user_id = str(args.get("user_id") or "").strip()
            text = str(args.get("text") or "").strip()
            title = str(args.get("title") or "").strip()
            if not tenant_id or not user_id or not text:
                return {"ok": False, "error": "tenant_id, user_id, text are required"}
            source = f"builtin:tenant:{tenant_id}:kb"
            if title:
                source = f"{source}:{title[:48]}"
            cid = _chunk_id(source, text)
            store = get_assistant_store()
            store.upsert_knowledge_chunk(
                chunk_id=cid,
                source=source,
                content=text,
                metadata={"tenant_id": tenant_id, "user_id": user_id, "title": title, "source": source},
            )
            client = build_default_embedding_client()
            emb = client.embed(text[:8000])
            store.upsert_knowledge_embedding(chunk_id=cid, model=emb.model, vector=emb.vector)
            return {"ok": True, "chunk_id": cid, "source": source, "embedding_model": emb.model}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="kb_add",
        description="Add a knowledge snippet for a tenant into the vector knowledge base.",
        parameters={
            "type": "object",
            "properties": {"tenant_id": {"type": "string"}, "user_id": {"type": "string"}, "title": {"type": "string", "description": "Optional title/label."}, "text": {"type": "string", "description": "Knowledge content to store."}},
            "required": ["tenant_id", "user_id", "text"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "rag", "write"}),
    )


def kb_search_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            tenant_id = str(args.get("tenant_id") or "").strip()
            query = str(args.get("query") or "").strip()
            limit = int(args.get("limit") or 3)
            if not tenant_id or not query:
                return {"ok": False, "error": "tenant_id and query are required"}
            store = get_assistant_store()
            from runtime.orchestration.memory import retrieve_context

            rows = retrieve_context(store, query, limit=max(1, min(limit, 6)))
            filtered = [r for r in rows if str(r.get("source") or "").startswith(f"builtin:tenant:{tenant_id}:")]
            hits = filtered[: max(1, min(limit, 6))]
            if not hits:
                like_rows = store.search_knowledge(query=query, limit=max(1, min(limit, 6)))
                hits = [r for r in like_rows if str(r.get("source") or "").startswith(f"builtin:tenant:{tenant_id}:")][: max(1, min(limit, 6))]
            refs = []
            for h in hits:
                refs.append({"source": str(h.get("source") or ""), "snippet": str(h.get("content") or "")[:240]})
            return {"ok": True, "hits": refs}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return ToolSpec(
        name="kb_search",
        description="Search tenant knowledge base and return citations/snippets.",
        parameters={
            "type": "object",
            "properties": {"tenant_id": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer", "default": 3}},
            "required": ["tenant_id", "query"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"productivity", "rag"}),
    )


__all__ = ["kb_add_tool", "kb_search_tool"]
