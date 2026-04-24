from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import yaml


@dataclass(frozen=True, slots=True)
class ParsedHookFrontmatter:
    frontmatter: Dict[str, Any]
    body: str


def parse_frontmatter(markdown: str) -> ParsedHookFrontmatter:
    """
    Parse YAML frontmatter delimited by leading '---' lines.
    Returns (frontmatter_dict, remaining_body).
    """
    text = markdown.lstrip("\ufeff")
    if not text.startswith("---"):
        return ParsedHookFrontmatter(frontmatter={}, body=markdown)

    lines = text.splitlines(keepends=True)
    if not lines:
        return ParsedHookFrontmatter(frontmatter={}, body=markdown)

    # first line is '---'
    if not lines[0].strip().startswith("---"):
        return ParsedHookFrontmatter(frontmatter={}, body=markdown)

    fm_lines = []
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip().startswith("---"):
            end_idx = i
            break
        fm_lines.append(lines[i])

    if end_idx is None:
        return ParsedHookFrontmatter(frontmatter={}, body=markdown)

    fm_raw = "".join(fm_lines)
    body = "".join(lines[end_idx + 1 :])

    try:
        parsed = yaml.safe_load(fm_raw) or {}
        if not isinstance(parsed, dict):
            parsed = {}
    except Exception:
        parsed = {}
    return ParsedHookFrontmatter(frontmatter=parsed, body=body)


def resolve_openclaw_metadata(frontmatter: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    OpenClaw embeds metadata as a JSON-like object under key 'metadata' -> 'openclaw'
    (or sometimes as already-parsed dict). We normalize to a dict if present.
    """
    meta = frontmatter.get("metadata")
    if not isinstance(meta, dict):
        return None
    oc = meta.get("openclaw")
    return oc if isinstance(oc, dict) else None


def resolve_hook_key(name: str, entry: Dict[str, Any]) -> str:
    # OpenClaw's TS resolves a config key with possible explicit hookKey; keep it simple.
    md = entry.get("metadata") if isinstance(entry, dict) else None
    if isinstance(md, dict):
        hook_key = md.get("hookKey")
        if isinstance(hook_key, str) and hook_key.strip():
            return hook_key.strip()
    return name

