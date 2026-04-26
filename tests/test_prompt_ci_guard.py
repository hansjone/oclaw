from __future__ import annotations

from pathlib import Path

from oclaw.platform.config.paths import PROJECT_ROOT


_PROMPT_CRITICAL_FILES = (
    "runtime/chat/agent.py",
    "runtime/agents/network_ops_agent.py",
    "runtime/agents/factory.py",
    "runtime/chat/agent_messages.py",
    "runtime/system_prompt.py",
    "runtime/memory_stage.py",
    "runtime/project_context_prompt.py",
    "runtime/chat/agent_errors.py",
    "platform/llm/image_message_client.py",
    "runtime/gateway.py",
)


def test_prompt_critical_paths_use_prompt_templates() -> None:
    for rel in _PROMPT_CRITICAL_FILES:
        text = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
        assert (
            "render_prompt(" in text
            or "render_prompt_for_lang(" in text
            or "render_runtime_prompt(" in text
        ), (
            f"{rel} must render prompts from oclaw/prompts*.md"
        )


def test_prompt_markdown_frontmatter_keys_present() -> None:
    roots = [
        PROJECT_ROOT / "prompts",
        PROJECT_ROOT / "prompts_runtime",
    ]
    for prompts_root in roots:
        for p in prompts_root.rglob("*.md"):
            if p.name == "MAPPING.md":
                continue
            raw = p.read_text(encoding="utf-8-sig")
            # Some legacy prompt bodies (not templates) are intentionally frontmatter-free.
            # CI only enforces frontmatter keys when frontmatter exists.
            if not raw.startswith("---\n"):
                continue
            assert "\n---\n" in raw, f"{p} missing frontmatter end"
            fm = raw.split("\n---\n", 1)[0]
            assert "title:" in fm, f"{p} missing title"
            assert "summary:" in fm, f"{p} missing summary"
            assert "read_when:" in fm, f"{p} missing read_when"

