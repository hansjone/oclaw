from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EmbeddingResult:
    model: str
    vector: list[float]


class EmbeddingClient:
    def embed(self, text: str) -> EmbeddingResult:
        raise NotImplementedError


class OpenAIEmbeddingClient(EmbeddingClient):
    def __init__(self, *, model: str | None = None, api_key: str | None = None, base_url: str | None = None):
        self.model = (model or os.getenv("OPENAI_EMBEDDING_MODEL") or "text-embedding-3-small").strip()
        self.api_key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "").strip() or None
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for embeddings")
        from openai import OpenAI

        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)

    def embed(self, text: str) -> EmbeddingResult:
        t = (text or "").strip()
        if not t:
            return EmbeddingResult(model=self.model, vector=[0.0] * 8)
        resp = self._client.embeddings.create(model=self.model, input=t)
        vec = list(resp.data[0].embedding)
        return EmbeddingResult(model=self.model, vector=[float(x) for x in vec])


class HashEmbeddingClient(EmbeddingClient):
    """Offline fallback: deterministic small vector (NOT semantic)."""

    def __init__(self, *, dim: int = 32, model: str = "hash-embed-32"):
        self.dim = int(dim)
        self.model = model

    def embed(self, text: str) -> EmbeddingResult:
        t = (text or "").encode("utf-8", errors="ignore")
        h = hashlib.sha256(t).digest()
        vec = []
        for i in range(self.dim):
            b = h[i % len(h)]
            vec.append((float(b) / 255.0) * 2.0 - 1.0)
        return EmbeddingResult(model=self.model, vector=vec)


def build_default_embedding_client() -> EmbeddingClient:
    mode = (os.getenv("AIA_RAG_EMBEDDING_MODE") or "").strip().lower()
    if mode in ("hash", "offline"):
        return HashEmbeddingClient()
    try:
        return OpenAIEmbeddingClient()
    except Exception:
        return HashEmbeddingClient()


__all__ = [
    "EmbeddingClient",
    "EmbeddingResult",
    "OpenAIEmbeddingClient",
    "HashEmbeddingClient",
    "build_default_embedding_client",
]

