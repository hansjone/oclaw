from __future__ import annotations

from oclaw.runtime.memory_stage import render_memory_context_block
from oclaw.runtime.types import OclawMemoryContext
from oclaw.prompts.loader import render_runtime_prompt


def test_router_prompt_renders() -> None:
    txt = render_runtime_prompt(
        "router/decide_route.md",
        variables={"user_text": "hi", "has_attachments": "no"},
        strict=True,
    )
    assert "json" in txt.lower()
    assert "sync_direct" in txt
    assert "async_task" in txt


def test_memory_context_markdown_block() -> None:
    ctx = OclawMemoryContext(
        short_term=("用户想排查网络问题",),
        semantic_hits=({"content": "上次 DNS 配置异常", "score": 0.91},),
    )
    out = render_memory_context_block(ctx)
    assert "[short_term_digest]" in out
    assert "[semantic_memory_hits]" in out

