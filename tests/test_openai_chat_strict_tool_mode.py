"""DeepSeek OpenAI-compat: strict_tool_mode via extra_body."""

from __future__ import annotations

import os
import unittest

from svc.llm.transports.openai_chat_completions import (
    _deepseek_strict_tool_mode_enabled,
    _merge_deepseek_strict_tool_mode_extra_body,
)


class DeepseekStrictToolModeTests(unittest.TestCase):
    def test_enabled_when_deepseek_in_base_url(self) -> None:
        self.assertTrue(
            _deepseek_strict_tool_mode_enabled(
                base_url="https://api.deepseek.com/v1",
                model="deepseek-chat",
            )
        )

    def test_disabled_when_env_off(self) -> None:
        prev = os.environ.get("AIA_DEEPSEEK_STRICT_TOOL_MODE")
        try:
            os.environ["AIA_DEEPSEEK_STRICT_TOOL_MODE"] = "0"
            self.assertFalse(
                _deepseek_strict_tool_mode_enabled(
                    base_url="https://api.deepseek.com/v1",
                    model="x",
                )
            )
        finally:
            if prev is None:
                os.environ.pop("AIA_DEEPSEEK_STRICT_TOOL_MODE", None)
            else:
                os.environ["AIA_DEEPSEEK_STRICT_TOOL_MODE"] = prev

    def test_merge_sets_extra_body_strict_tool_mode(self) -> None:
        kwargs: dict = {"model": "m", "messages": [], "stream": False, "tools": [{"type": "function"}]}
        _merge_deepseek_strict_tool_mode_extra_body(
            kwargs,
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            use_tools=True,
        )
        self.assertEqual(kwargs.get("extra_body"), {"strict_tool_mode": True})

    def test_merge_preserves_existing_extra_body(self) -> None:
        kwargs: dict = {
            "model": "m",
            "messages": [],
            "stream": False,
            "tools": [{"type": "function"}],
            "extra_body": {"thinking": {"type": "disabled"}},
        }
        _merge_deepseek_strict_tool_mode_extra_body(
            kwargs,
            base_url="https://api.deepseek.com",
            model="deepseek-reasoner",
            use_tools=True,
        )
        self.assertEqual(
            kwargs["extra_body"],
            {"thinking": {"type": "disabled"}, "strict_tool_mode": True},
        )

    def test_merge_skips_without_tools(self) -> None:
        kwargs: dict = {"model": "m", "messages": [], "stream": False}
        _merge_deepseek_strict_tool_mode_extra_body(
            kwargs,
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            use_tools=False,
        )
        self.assertNotIn("extra_body", kwargs)

    def test_merge_skips_non_deepseek(self) -> None:
        kwargs: dict = {"model": "m", "messages": [], "stream": False, "tools": [{"type": "function"}]}
        _merge_deepseek_strict_tool_mode_extra_body(
            kwargs,
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            use_tools=True,
        )
        self.assertNotIn("extra_body", kwargs)


if __name__ == "__main__":
    unittest.main()
