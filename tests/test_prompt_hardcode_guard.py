from __future__ import annotations

from pathlib import Path

from oclaw.platform.config.paths import PROJECT_ROOT


def _read(rel: str) -> str:
    return (PROJECT_ROOT / rel).read_text(encoding="utf-8")


def test_no_legacy_inline_manager_prompts() -> None:
    # Manager orchestrator was removed; keep this test as a smoke-guard for any new inline
    # manager-style prompt leakage into the runtime entrypoints.
    content = _read("runtime/gateway.py")
    assert "【重要：只返回合法 JSON】" not in content
    assert "你是 AI 助手的路由（Routing）智能体" not in content


def test_no_legacy_inline_specialist_prompts() -> None:
    content = _read("runtime/agents/specialists.py")
    assert "【最高优先级执行规则（必须遵守）】" not in content
    assert "【职责范围】" not in content


def test_no_legacy_inline_runtime_prompt() -> None:
    content = _read("runtime/chat/agent.py")
    assert "你是一个通用 AI 助手。" not in content

