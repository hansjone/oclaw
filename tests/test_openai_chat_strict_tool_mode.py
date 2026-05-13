"""DeepSeek: per-function ``strict: true`` on tools (official Tool Calls / strict Beta)."""

from __future__ import annotations

import os
import unittest

from svc.llm.transports.openai_chat_completions import (
    _apply_deepseek_strict_tools,
    _deepseek_strict_tools_enabled,
)


class DeepseekStrictToolsTests(unittest.TestCase):
    def test_enabled_when_deepseek_in_base_url(self) -> None:
        self.assertTrue(
            _deepseek_strict_tools_enabled(
                base_url="https://api.deepseek.com/v1",
                model="deepseek-chat",
            )
        )

    def test_disabled_when_env_off(self) -> None:
        prev = os.environ.get("AIA_DEEPSEEK_STRICT_TOOL_MODE")
        try:
            os.environ["AIA_DEEPSEEK_STRICT_TOOL_MODE"] = "0"
            self.assertFalse(
                _deepseek_strict_tools_enabled(
                    base_url="https://api.deepseek.com/v1",
                    model="x",
                )
            )
        finally:
            if prev is None:
                os.environ.pop("AIA_DEEPSEEK_STRICT_TOOL_MODE", None)
            else:
                os.environ["AIA_DEEPSEEK_STRICT_TOOL_MODE"] = prev

    def test_apply_sets_strict_on_function_tools(self) -> None:
        tools = [
            {"type": "function", "function": {"name": "get_weather", "parameters": {"type": "object", "properties": {}}}},
            {"type": "not_function", "x": 1},
        ]
        out = _apply_deepseek_strict_tools(tools)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertTrue(out[0]["function"]["strict"])
        self.assertEqual(out[1].get("type"), "not_function")
        self.assertNotIn("strict", out[1])
        # input not mutated
        self.assertNotIn("strict", tools[0].get("function", {}))

    def test_apply_skips_non_deepseek_not_tested_here(self) -> None:
        out = _apply_deepseek_strict_tools([])
        self.assertEqual(out, [])

    def test_apply_handles_missing_function_dict(self) -> None:
        out = _apply_deepseek_strict_tools([{"type": "function"}])
        assert out is not None
        self.assertEqual(out[0]["function"], {"strict": True})


if __name__ == "__main__":
    unittest.main()
