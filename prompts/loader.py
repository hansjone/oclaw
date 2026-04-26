from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.prompts.frontmatter import parse_markdown_document

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


@dataclass(frozen=True)
class PromptDoc:
    frontmatter: dict[str, Any]
    body: str


def _prompts_root() -> Path:
    return (PROJECT_ROOT / "prompts").resolve()


def _runtime_prompts_root() -> Path:
    # Runtime prompts are unified into the single prompts tree.
    return _prompts_root()


@lru_cache(maxsize=512)
def load_prompt_doc(prompt_path: str) -> PromptDoc:
    p = (_prompts_root() / str(prompt_path)).resolve()
    if not p.exists():
        raise FileNotFoundError(f"prompt not found: {prompt_path}")
    raw = p.read_text(encoding="utf-8")
    fm, body = parse_markdown_document(raw, source=f"prompt:{prompt_path}")
    return PromptDoc(frontmatter=fm, body=body)


@lru_cache(maxsize=512)
def load_runtime_prompt_doc(prompt_path: str) -> PromptDoc:
    p = (_runtime_prompts_root() / str(prompt_path)).resolve()
    if not p.exists():
        raise FileNotFoundError(f"runtime prompt not found: {prompt_path}")
    raw = p.read_text(encoding="utf-8")
    fm, body = parse_markdown_document(raw, source=f"runtime_prompt:{prompt_path}")
    return PromptDoc(frontmatter=fm, body=body)


def render_prompt_for_lang(stem: str, lang: str, *, variables: dict[str, Any] | None = None, strict: bool = True) -> str:
    suf = "en" if (lang or "zh").strip().lower().startswith("en") else "zh"
    return render_prompt(f"{stem}.{suf}.md", variables=variables, strict=strict)


def render_prompt(prompt_path: str, *, variables: dict[str, Any] | None = None, strict: bool = True) -> str:
    doc = load_prompt_doc(prompt_path)
    vars_in = dict(variables or {})
    missing: set[str] = set()

    def _repl(m: re.Match[str]) -> str:
        key = str(m.group(1) or "")
        if key in vars_in:
            return str(vars_in.get(key) or "")
        missing.add(key)
        return ""

    out = _VAR_RE.sub(_repl, doc.body)
    if strict and missing:
        raise ValueError(f"missing prompt variables for {prompt_path}: {', '.join(sorted(missing))}")
    return out.strip()


def render_runtime_prompt(prompt_path: str, *, variables: dict[str, Any] | None = None, strict: bool = True) -> str:
    doc = load_runtime_prompt_doc(prompt_path)
    vars_in = dict(variables or {})
    missing: set[str] = set()

    def _repl(m: re.Match[str]) -> str:
        key = str(m.group(1) or "")
        if key in vars_in:
            return str(vars_in.get(key) or "")
        missing.add(key)
        return ""

    out = _VAR_RE.sub(_repl, doc.body)
    if strict and missing:
        raise ValueError(f"missing runtime prompt variables for {prompt_path}: {', '.join(sorted(missing))}")
    return out.strip()


__all__ = [
    "PromptDoc",
    "load_prompt_doc",
    "load_runtime_prompt_doc",
    "render_prompt",
    "render_prompt_for_lang",
    "render_runtime_prompt",
]
