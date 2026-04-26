from __future__ import annotations

import copy
import threading
from pathlib import Path
from typing import Any

from oclaw.platform.config.paths import PROJECT_ROOT

_REQUIRED_FILES: tuple[str, ...] = ("SOUL.md",)
_OPTIONAL_FILES: tuple[str, ...] = ("ROLE_SYSTEM.md",)
_ALL_FILES: tuple[str, ...] = (*_REQUIRED_FILES, *_OPTIONAL_FILES)
_RESERVED_IDS: frozenset[str] = frozenset({"main"})
_CACHE_LOCK = threading.Lock()
_LIST_CACHE_SIGNATURE: tuple[Any, ...] | None = None
_LIST_CACHE_ROWS: list[dict[str, Any]] = []
_CATALOG_CACHE: dict[tuple[Any, ...], str] = {}
_SPECIALIST_IDS_CACHE: dict[tuple[Any, ...], tuple[str, ...]] = {}


def workspaces_root() -> Path:
    return (PROJECT_ROOT / "runtime" / "workspaces").resolve()


def normalize_expert_id(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    out: list[str] = []
    for ch in text:
        if ch.isalnum() or ch in {"-", "_"}:
            out.append(ch)
        elif ch.isspace():
            out.append("-")
    return "".join(out).strip("-_")


def is_builtin_expert(expert_id: str) -> bool:
    return normalize_expert_id(expert_id) in _RESERVED_IDS


def _workspace_signature() -> tuple[Any, ...]:
    root = workspaces_root()
    if not root.exists() or not root.is_dir():
        return ("missing",)
    rows: list[tuple[str, str, int, int]] = []
    for item in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not item.is_dir():
            continue
        if item.name.startswith("__"):
            continue
        eid = normalize_expert_id(item.name)
        if not eid:
            continue
        for name in _ALL_FILES:
            p = item / name
            if not p.exists() or not p.is_file():
                continue
            try:
                st = p.stat()
                rows.append((eid, name, int(getattr(st, "st_mtime_ns", 0)), int(st.st_size)))
            except Exception:
                continue
    return tuple(rows)


def expert_workspace_signature_token() -> tuple[Any, ...]:
    """Stable token for cache invalidation when workspace files change."""
    return _workspace_signature()


def _clear_experts_cache() -> None:
    global _LIST_CACHE_SIGNATURE, _LIST_CACHE_ROWS
    with _CACHE_LOCK:
        _LIST_CACHE_SIGNATURE = None
        _LIST_CACHE_ROWS = []
        _CATALOG_CACHE.clear()
        _SPECIALIST_IDS_CACHE.clear()


def _normalize_supported_files(files: dict[str, Any] | None) -> dict[str, str]:
    raw = files if isinstance(files, dict) else {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        name = str(k or "").strip()
        if not name:
            continue
        if name not in _ALL_FILES:
            raise ValueError("unsupported_file_name")
        out[name] = str(v or "")
    return out


def list_experts() -> list[dict[str, Any]]:
    global _LIST_CACHE_SIGNATURE, _LIST_CACHE_ROWS
    sig = _workspace_signature()
    with _CACHE_LOCK:
        if _LIST_CACHE_SIGNATURE == sig:
            return copy.deepcopy(_LIST_CACHE_ROWS)
    root = workspaces_root()
    out: list[dict[str, Any]] = []
    if not root.exists() or not root.is_dir():
        with _CACHE_LOCK:
            _LIST_CACHE_SIGNATURE = sig
            _LIST_CACHE_ROWS = []
            _CATALOG_CACHE.clear()
        return out
    for item in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not item.is_dir():
            continue
        eid = normalize_expert_id(item.name)
        if not eid:
            continue
        files: dict[str, str] = {}
        for name in _ALL_FILES:
            p = item / name
            if not p.exists() or not p.is_file():
                files[name] = ""
                continue
            try:
                files[name] = p.read_text(encoding="utf-8")
            except Exception:
                files[name] = ""
        out.append(
            {
                "id": eid,
                "path": str(item),
                "builtin": is_builtin_expert(eid),
                "has_required_soul": bool(str(files.get("SOUL.md") or "").strip()),
                "files": files,
            }
        )
    with _CACHE_LOCK:
        _LIST_CACHE_SIGNATURE = sig
        _LIST_CACHE_ROWS = copy.deepcopy(out)
        _CATALOG_CACHE.clear()
    return out


def _one_line_summary(text: str, *, limit: int = 120) -> str:
    s = " ".join(str(text or "").strip().split())
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 1)] + "…"


def build_expert_catalog_block(*, include_main: bool = False, per_field_limit: int = 120, max_total_chars: int = 4000) -> str:
    sig = _workspace_signature()
    cache_key = (sig, bool(include_main), int(per_field_limit), int(max_total_chars))
    with _CACHE_LOCK:
        cached = _CATALOG_CACHE.get(cache_key)
    if isinstance(cached, str):
        return cached
    rows = list_experts()
    lines: list[str] = []
    for row in rows:
        eid = str(row.get("id") or "").strip().lower()
        if not eid:
            continue
        if not include_main and eid == "main":
            continue
        if eid in {"pycache", "__pycache__"} or eid.endswith("pycache"):
            continue
        if not bool(row.get("has_required_soul")):
            continue
        files = row.get("files") if isinstance(row, dict) else {}
        f = files if isinstance(files, dict) else {}
        role_system = _one_line_summary(str(f.get("ROLE_SYSTEM.md") or ""), limit=per_field_limit)
        soul = _one_line_summary(str(f.get("SOUL.md") or ""), limit=per_field_limit)
        bits: list[str] = [f"- {eid}"]
        if role_system:
            bits.append(f"role_system={role_system}")
        if soul:
            bits.append(f"soul={soul}")
        line = " | ".join(bits)
        lines.append(line)
    out = "\n".join(lines).strip()
    if len(out) > max_total_chars:
        out = out[: max_total_chars - 1] + "…"
    with _CACHE_LOCK:
        _CATALOG_CACHE[cache_key] = out
    return out


def discover_specialist_ids_from_workspaces(
    *,
    base_order: tuple[str, ...] = ("generalist", "ops", "image", "memory"),
) -> tuple[str, ...]:
    sig = _workspace_signature()
    cache_key = (sig, tuple(str(x).strip().lower() for x in base_order if str(x).strip()))
    with _CACHE_LOCK:
        cached = _SPECIALIST_IDS_CACHE.get(cache_key)
    if isinstance(cached, tuple):
        return cached
    discovered: list[str] = []
    for row in list_experts():
        sid = str(row.get("id") or "").strip().lower()
        if not sid or sid == "main":
            continue
        # Ignore cache-like directories and malformed expert folders.
        if sid in {"pycache", "__pycache__"} or sid.endswith("pycache"):
            continue
        if not bool(row.get("has_required_soul")):
            continue
        discovered.append(sid)
    ordered: list[str] = []
    for sid in cache_key[1]:
        if sid not in ordered:
            ordered.append(sid)
    for sid in discovered:
        if sid not in ordered:
            ordered.append(sid)
    out = tuple(ordered)
    with _CACHE_LOCK:
        _SPECIALIST_IDS_CACHE[cache_key] = out
    return out


def warm_expert_workspace_cache() -> None:
    _ = list_experts()
    _ = build_expert_catalog_block(include_main=False, per_field_limit=120, max_total_chars=4000)
    _ = discover_specialist_ids_from_workspaces()


def _workspace_dir(expert_id: str) -> Path:
    eid = normalize_expert_id(expert_id)
    if not eid:
        raise ValueError("invalid_expert_id")
    return (workspaces_root() / eid).resolve()


def create_expert(*, expert_id: str, files: dict[str, Any]) -> dict[str, Any]:
    eid = normalize_expert_id(expert_id)
    if not eid or eid in _RESERVED_IDS:
        raise ValueError("invalid_expert_id")
    root = workspaces_root()
    root.mkdir(parents=True, exist_ok=True)
    target = (root / eid).resolve()
    if target.exists():
        raise ValueError("expert_exists")
    clean_files = _normalize_supported_files(files)
    soul = str(clean_files.get("SOUL.md") or "").strip()
    if not soul:
        raise ValueError("soul_required")
    target.mkdir(parents=True, exist_ok=False)
    for name in _ALL_FILES:
        body = str(clean_files.get(name) or "")
        if name in _REQUIRED_FILES and not body.strip():
            continue
        if body:
            (target / name).write_text(body.strip() + "\n", encoding="utf-8")
    if not (target / "SOUL.md").exists():
        (target / "SOUL.md").write_text(soul + "\n", encoding="utf-8")
    _clear_experts_cache()
    return {"id": eid, "path": str(target)}


def update_expert_files(*, expert_id: str, files: dict[str, Any]) -> dict[str, Any]:
    eid = normalize_expert_id(expert_id)
    if not eid:
        raise ValueError("invalid_expert_id")
    target = _workspace_dir(eid)
    if not target.exists() or not target.is_dir():
        raise ValueError("expert_not_found")
    clean_files = _normalize_supported_files(files)
    next_files: dict[str, str] = {}
    for name in _ALL_FILES:
        if name in clean_files:
            next_files[name] = str(clean_files.get(name) or "")
        else:
            p = target / name
            next_files[name] = p.read_text(encoding="utf-8") if p.exists() and p.is_file() else ""
    if not str(next_files.get("SOUL.md") or "").strip():
        raise ValueError("soul_required")
    for name in _ALL_FILES:
        p = target / name
        body = str(next_files.get(name) or "")
        if body.strip():
            p.write_text(body.strip() + "\n", encoding="utf-8")
        elif p.exists():
            p.unlink()
    _clear_experts_cache()
    return {"id": eid, "path": str(target)}


def delete_expert(expert_id: str) -> None:
    eid = normalize_expert_id(expert_id)
    if not eid:
        raise ValueError("invalid_expert_id")
    if is_builtin_expert(eid):
        raise ValueError("builtin_expert_protected")
    target = (workspaces_root() / eid).resolve()
    if not target.exists() or not target.is_dir():
        raise ValueError("expert_not_found")
    for p in sorted(target.glob("**/*"), reverse=True):
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            p.rmdir()
    target.rmdir()
    _clear_experts_cache()


__all__ = [
    "build_expert_catalog_block",
    "create_expert",
    "delete_expert",
    "discover_specialist_ids_from_workspaces",
    "expert_workspace_signature_token",
    "is_builtin_expert",
    "list_experts",
    "normalize_expert_id",
    "update_expert_files",
    "warm_expert_workspace_cache",
    "workspaces_root",
]
