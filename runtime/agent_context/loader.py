from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

from svc.config.paths import PROJECT_ROOT

_ROLE_CONTEXT_CACHE_LOCK = threading.Lock()
_ROLE_CONTEXT_CACHE: dict[tuple[str, tuple[Any, ...], tuple[tuple[str, str], ...]], str] = {}
_ROLE_DOCS: tuple[str, ...] = ("SOUL.md", "SOUL.en.md", "ROLE_SYSTEM.md", "ROLE_SYSTEM.en.md")
_TEMPLATE_VAR_RE = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def _read_text(path: Path) -> str:
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return ""
    return ""


def _workspace_for_role(role: str) -> str:
    r = str(role or "").strip().lower()
    if r == "manager":
        return "main"
    return r or "generalist"


def _role_workspace_signature(role_id: str) -> tuple[Any, ...]:
    base = (PROJECT_ROOT / "runtime" / "workspaces").resolve()
    role_root = (base / role_id).resolve()
    if not role_root.exists() or not role_root.is_dir():
        return ("missing", role_id, str(base))
    rows: list[tuple[str, int, int]] = []
    for name in _ROLE_DOCS:
        p = role_root / name
        if not p.exists() or not p.is_file():
            rows.append((name, 0, 0))
            continue
        try:
            st = p.stat()
            rows.append((name, int(getattr(st, "st_mtime_ns", 0)), int(st.st_size)))
        except Exception:
            rows.append((name, 0, 0))
    return (str(role_root), *tuple(rows))


def _normalize_template_vars(template_vars: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    if not isinstance(template_vars, dict):
        return tuple()
    pairs: list[tuple[str, str]] = []
    for k, v in template_vars.items():
        key = str(k or "").strip()
        if not key:
            continue
        pairs.append((key, str(v or "").strip()))
    pairs.sort(key=lambda x: x[0])
    return tuple(pairs)


def _render_template_vars(text: str, vars_tuple: tuple[tuple[str, str], ...]) -> str:
    if not text:
        return ""
    if not vars_tuple:
        return text
    vars_map = {k: v for k, v in vars_tuple}

    def _replace(m: re.Match[str]) -> str:
        name = str(m.group(1) or "").strip()
        return vars_map.get(name, m.group(0))

    return _TEMPLATE_VAR_RE.sub(_replace, text)


def _read_localized_doc(root: Path, base: str, *, lang: str) -> str:
    """Prefer ``ROLE_SYSTEM.en.md`` when lang is en; fall back to ``ROLE_SYSTEM.md``."""
    lang_en = str(lang or "").strip().lower().startswith("en")
    if lang_en and base.endswith(".md"):
        localized = base[:-3] + ".en.md"
        text = _read_text(root / localized)
        if text:
            return text
    return _read_text(root / base)


def build_role_system_context(
    role: str,
    template_vars: dict[str, Any] | None = None,
    *,
    lang: str = "zh",
) -> str:
    """Build role context from runtime/workspaces/<role>."""
    role_id = _workspace_for_role(role)
    lang_key = "en" if str(lang or "").strip().lower().startswith("en") else "zh"
    sig = _role_workspace_signature(role_id)
    vars_tuple = _normalize_template_vars(template_vars)
    cache_key = (role_id, lang_key, sig, vars_tuple)
    with _ROLE_CONTEXT_CACHE_LOCK:
        cached = _ROLE_CONTEXT_CACHE.get(cache_key)
    if isinstance(cached, str) and cached.strip():
        return cached
    base = (PROJECT_ROOT / "runtime" / "workspaces").resolve()
    roots: list[Path] = []
    role_root = (base / role_id).resolve()
    if role_root.exists() and role_root.is_dir():
        roots.append(role_root)
    parts: list[str] = []
    for name in ("SOUL.md",):
        t = ""
        for root in roots:
            t = _read_localized_doc(root, name, lang=lang_key)
            if t:
                t = _render_template_vars(t, vars_tuple)
            if t:
                break
        if t:
            parts.append(f"# SOUL\n{t}")
    role_system = ""
    for root in roots:
        role_system = _read_localized_doc(root, "ROLE_SYSTEM.md", lang=lang_key)
        if role_system:
            role_system = _render_template_vars(role_system, vars_tuple)
            break
    if not role_system:
        role_system = (
            "You are a professional assistant. Lead with verifiable conclusions, then evidence and next steps."
            if lang_key == "en"
            else "你是专业助手。先给可验证结论，再给依据与下一步。"
        )
    parts.append(f"# ROLE_SYSTEM\n{role_system}")
    out = "\n\n".join([p for p in parts if p.strip()]).strip()
    with _ROLE_CONTEXT_CACHE_LOCK:
        _ROLE_CONTEXT_CACHE[cache_key] = out
        if len(_ROLE_CONTEXT_CACHE) > 64:
            _ROLE_CONTEXT_CACHE.clear()
            _ROLE_CONTEXT_CACHE[cache_key] = out
    return out


__all__ = ["build_role_system_context"]

