from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oclaw.platform.embeddings.embedding_client import build_default_embedding_client
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.platform.config.paths import PROJECT_ROOT


def _default_workspace_root() -> Path:
    import os

    override = (os.getenv("AIA_WORKSPACE_ROOT") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(PROJECT_ROOT).resolve()


@dataclass(frozen=True)
class IndexStats:
    files_seen: int
    chunks_upserted: int
    embeddings_upserted: int


def _chunk_id(source: str, text: str) -> str:
    raw = f"{source}\n{text}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()


def _iter_files(root: Path, patterns: list[str], *, max_files: int) -> list[Path]:
    files: list[Path] = []
    for pat in patterns:
        for p in root.glob(pat):
            if p.is_dir():
                continue
            files.append(p)
            if len(files) >= max_files:
                return files
    # de-dup by path
    uniq = []
    seen = set()
    for p in files:
        rp = str(p)
        if rp in seen:
            continue
        seen.add(rp)
        uniq.append(p)
    return uniq[:max_files]


def index_workspace(
    store: SqliteStore,
    *,
    root: str | None = None,
    patterns: list[str] | None = None,
    max_files: int = 200,
    max_chars_per_chunk: int = 1600,
) -> IndexStats:
    r = Path(root).resolve() if root else _default_workspace_root()
    pats = patterns or ["**/*.py", "README*.md", "**/*.md"]
    files = _iter_files(r, pats, max_files=max(1, int(max_files)))
    client = build_default_embedding_client()
    chunks_upserted = 0
    embeds_upserted = 0

    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(p.relative_to(r))
        # naive chunking by chars (good enough for MVP)
        for idx in range(0, len(text), max(200, int(max_chars_per_chunk))):
            chunk = text[idx : idx + int(max_chars_per_chunk)].strip()
            if not chunk:
                continue
            source = f"workspace:{rel}#c{idx//max_chars_per_chunk:04d}"
            cid = _chunk_id(source, chunk)
            store.upsert_knowledge_chunk(
                chunk_id=cid,
                source=source,
                content=chunk,
                metadata={"source": source, "path": rel, "offset": idx},
            )
            chunks_upserted += 1
            try:
                emb = client.embed(chunk[:8000])
                store.upsert_knowledge_embedding(chunk_id=cid, model=emb.model, vector=emb.vector)
                embeds_upserted += 1
            except Exception:
                continue

    return IndexStats(files_seen=len(files), chunks_upserted=chunks_upserted, embeddings_upserted=embeds_upserted)


__all__ = ["IndexStats", "index_workspace"]

