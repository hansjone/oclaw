from __future__ import annotations

import json
import os
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - requirements.txt includes PyYAML
    yaml = None  # type: ignore[assignment]


def split_markdown_frontmatter(raw: str) -> tuple[str, str]:
    """Split leading YAML frontmatter from markdown body (oclaw-style `---` fences)."""
    txt = str(raw or "")
    if not txt.startswith("---\n"):
        return "", txt
    end = txt.find("\n---\n", 4)
    if end < 0:
        return "", txt
    return txt[4:end], txt[end + 5 :]


def _legacy_line_parse(frontmatter_text: str) -> dict[str, Any]:
    """Best-effort key: value lines (pre-YAML migration compatibility)."""
    out: dict[str, Any] = {}
    for ln in str(frontmatter_text or "").splitlines():
        line = ln.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        key = str(k).strip()
        val = str(v).strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        out[key] = val
    meta_raw = str(out.get("metadata") or "").strip()
    if meta_raw:
        try:
            out["metadata"] = json.loads(meta_raw)
        except Exception:
            out["metadata"] = {}
    else:
        out["metadata"] = {}
    return out


def frontmatter_strict_yaml() -> bool:
    return str(os.getenv("AIA_PROMPT_FRONTMATTER_STRICT", "")).strip().lower() in {"1", "true", "yes", "on"}


def parse_frontmatter_dict(frontmatter_text: str, *, source: str = "prompt") -> dict[str, Any]:
    """
    Parse YAML frontmatter. On YAML failure, falls back to legacy line parser unless
    AIA_PROMPT_FRONTMATTER_STRICT is truthy (then raises).
    """
    text = str(frontmatter_text or "").strip()
    if not text:
        return {}
    strict = frontmatter_strict_yaml()
    if yaml is None:
        if strict:
            raise RuntimeError("PyYAML is required when AIA_PROMPT_FRONTMATTER_STRICT is enabled")
        return _legacy_line_parse(text)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        if strict:
            raise ValueError(f"invalid YAML frontmatter ({source}): {exc}") from exc
        return _legacy_line_parse(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        if strict:
            raise ValueError(f"frontmatter YAML root must be a mapping ({source})")
        return _legacy_line_parse(text)
    return dict(data)


def parse_markdown_document(raw: str, *, source: str = "markdown") -> tuple[dict[str, Any], str]:
    """Split file and parse frontmatter to a dict; body is stripped markdown."""
    fm_text, body = split_markdown_frontmatter(raw)
    meta = parse_frontmatter_dict(fm_text, source=source) if fm_text.strip() else {}
    return meta, str(body or "").strip()


__all__ = [
    "frontmatter_strict_yaml",
    "parse_frontmatter_dict",
    "parse_markdown_document",
    "split_markdown_frontmatter",
]
