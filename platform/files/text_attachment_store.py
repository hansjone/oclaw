from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from oclaw.platform.config.paths import attachments_dir


DEFAULT_TEXT_INLINE_MAX_CHARS = 12_000
DEFAULT_TEXT_CHUNK_SIZE = 1_600
DEFAULT_TEXT_CHUNK_OVERLAP = 200


def _text_root() -> Path:
    p = (attachments_dir() / "textual").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _text_id(attachment_id: str, name: str) -> str:
    raw = f"{attachment_id}:{name}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()


def _db_path(text_id: str) -> Path:
    return _text_root() / f"{text_id}.sqlite"


def _meta_path(text_id: str) -> Path:
    return _text_root() / f"{text_id}.meta.json"


def _is_valid_text_id(text_id: str) -> bool:
    tid = str(text_id or "").strip().lower()
    return bool(re.fullmatch(r"[0-9a-f]{64}", tid))


def _chunk_text(*, text: str, chunk_size: int, overlap: int) -> list[dict[str, Any]]:
    body = str(text or "")
    if not body:
        return []
    size = max(200, min(int(chunk_size or DEFAULT_TEXT_CHUNK_SIZE), 8_000))
    ov = max(0, min(int(overlap or DEFAULT_TEXT_CHUNK_OVERLAP), size - 1))
    chunks: list[dict[str, Any]] = []
    i = 0
    idx = 0
    n = len(body)
    while i < n:
        end = min(n, i + size)
        chunk = body[i:end]
        chunks.append({"chunk_index": idx, "start_char": i, "end_char": end, "content": chunk})
        if end >= n:
            break
        i = end - ov
        idx += 1
    return chunks


def save_text_document(
    *,
    attachment_id: str,
    name: str,
    text: str,
    source_kind: str,
    chunk_size: int = DEFAULT_TEXT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_TEXT_CHUNK_OVERLAP,
) -> dict[str, Any]:
    tid = _text_id(attachment_id=attachment_id, name=name)
    db = _db_path(tid)
    meta = _meta_path(tid)
    chunks = _chunk_text(text=str(text or ""), chunk_size=chunk_size, overlap=chunk_overlap)
    with sqlite3.connect(str(db)) as conn:
        conn.execute("DROP TABLE IF EXISTS text_chunks")
        conn.execute(
            (
                "CREATE TABLE text_chunks ("
                "chunk_index INTEGER NOT NULL, "
                "start_char INTEGER NOT NULL, "
                "end_char INTEGER NOT NULL, "
                "content TEXT NOT NULL)"
            )
        )
        for c in chunks:
            conn.execute(
                "INSERT INTO text_chunks(chunk_index,start_char,end_char,content) VALUES(?,?,?,?)",
                [
                    int(c.get("chunk_index") or 0),
                    int(c.get("start_char") or 0),
                    int(c.get("end_char") or 0),
                    str(c.get("content") or ""),
                ],
            )
        conn.commit()
    payload = {
        "text_id": tid,
        "attachment_id": str(attachment_id or ""),
        "name": str(name or ""),
        "source_kind": str(source_kind or "text"),
        "chars": int(len(str(text or ""))),
        "chunks": int(len(chunks)),
        "chunk_size": int(chunk_size),
        "chunk_overlap": int(chunk_overlap),
        "db_path": str(db),
    }
    meta.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def get_text_meta(text_id: str) -> dict[str, Any] | None:
    tid = str(text_id or "").strip()
    if not _is_valid_text_id(tid):
        return None
    p = _meta_path(tid)
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def query_text_document(
    *,
    text_id: str,
    query: str | None = None,
    top_k: int = 5,
    offset: int = 0,
) -> dict[str, Any]:
    tid = str(text_id or "").strip()
    if not _is_valid_text_id(tid):
        return {"ok": False, "error": "text_id_invalid_format"}
    meta = get_text_meta(tid)
    if not isinstance(meta, dict):
        return {"ok": False, "error": "text_not_found"}
    db = Path(str(meta.get("db_path") or ""))
    if not db.exists():
        return {"ok": False, "error": "text_store_missing"}
    lim = max(1, min(int(top_k or 5), 50))
    off = max(0, int(offset or 0))
    q = str(query or "").strip()
    rows: list[dict[str, Any]] = []
    with sqlite3.connect(str(db)) as conn:
        conn.row_factory = sqlite3.Row
        total = int(conn.execute("SELECT COUNT(1) AS n FROM text_chunks").fetchone()[0] or 0)
        if q:
            q_like = f"%{q.lower()}%"
            sql = (
                "SELECT chunk_index,start_char,end_char,content, "
                "(LENGTH(LOWER(content)) - LENGTH(REPLACE(LOWER(content), LOWER(?), ''))) / MAX(1, LENGTH(?)) AS score "
                "FROM text_chunks WHERE LOWER(content) LIKE ? "
                "ORDER BY score DESC, chunk_index ASC LIMIT ? OFFSET ?"
            )
            out = conn.execute(sql, [q, q, q_like, lim, off]).fetchall()
        else:
            out = conn.execute(
                "SELECT chunk_index,start_char,end_char,content, 0 AS score FROM text_chunks ORDER BY chunk_index ASC LIMIT ? OFFSET ?",
                [lim, off],
            ).fetchall()
        for r in out:
            rows.append(
                {
                    "chunk_index": int(r["chunk_index"] or 0),
                    "start_char": int(r["start_char"] or 0),
                    "end_char": int(r["end_char"] or 0),
                    "content": str(r["content"] or ""),
                    "score": float(r["score"] or 0.0),
                }
            )
    return {
        "ok": True,
        "text_id": tid,
        "name": str(meta.get("name") or ""),
        "source_kind": str(meta.get("source_kind") or "text"),
        "chars": int(meta.get("chars") or 0),
        "chunks_total": int(meta.get("chunks") or 0),
        "rows_total": int(total),
        "query": q,
        "rows": rows,
        "top_k": lim,
        "offset": off,
    }


__all__ = [
    "DEFAULT_TEXT_INLINE_MAX_CHARS",
    "DEFAULT_TEXT_CHUNK_SIZE",
    "DEFAULT_TEXT_CHUNK_OVERLAP",
    "save_text_document",
    "get_text_meta",
    "query_text_document",
]

