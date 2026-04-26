from __future__ import annotations

import pytest

from oclaw.prompts.loader import load_runtime_prompt_doc, load_prompt_doc, render_runtime_prompt, render_prompt


def test_load_prompt_doc_with_frontmatter() -> None:
    doc = load_prompt_doc("runtime/default_system.zh.md")
    assert doc.frontmatter.get("title") == "default_runtime_system_zh"
    assert "你是一个通用 AI 助手" in doc.body


def test_render_prompt_strict_missing_variable_raises() -> None:
    with pytest.raises(ValueError):
        render_prompt("tools/tool_result_unpaired.md", variables={"tag": "x"}, strict=True)


def test_render_prompt_success() -> None:
    out = render_prompt(
        "tools/tool_result_unpaired.md",
        variables={"tag": "tool_use_result:unpaired", "payload": "ok=true"},
        strict=True,
    )
    assert "[tool_use_result:unpaired]" in out
    assert "ok=true" in out


def test_load_runtime_prompt_doc_with_frontmatter() -> None:
    doc = load_runtime_prompt_doc("runtime/default_system.zh.md")
    assert doc.frontmatter.get("title") == "default_runtime_system_zh"
    assert "你是一个通用 AI 助手" in doc.body


def test_render_runtime_prompt_success() -> None:
    out = render_runtime_prompt(
        "runtime/project_context_block.md",
        variables={"project_context": "[AGENTS.md]\nfoo"},
        strict=True,
    )
    assert "[project_context]" in out
    assert "[AGENTS.md]" in out

