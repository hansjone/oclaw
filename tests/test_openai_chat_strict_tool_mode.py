"""OpenAI-style tools: optional ``function.strict: true`` (default on; env to disable)."""

from __future__ import annotations

import os
import unittest

from svc.llm.transports.openai_chat_completions import (
    _apply_strict_flag_to_function_tools,
    _openai_tool_function_strict_enabled,
)


class OpenAIToolFunctionStrictTests(unittest.TestCase):
    def test_enabled_by_default(self) -> None:
        prev = os.environ.pop("AIA_TOOL_FUNCTION_STRICT", None)
        try:
            self.assertTrue(_openai_tool_function_strict_enabled())
        finally:
            if prev is not None:
                os.environ["AIA_TOOL_FUNCTION_STRICT"] = prev

    def test_disabled_when_tool_function_strict_off(self) -> None:
        prev = os.environ.get("AIA_TOOL_FUNCTION_STRICT")
        try:
            os.environ["AIA_TOOL_FUNCTION_STRICT"] = "0"
            self.assertFalse(_openai_tool_function_strict_enabled())
        finally:
            if prev is None:
                os.environ.pop("AIA_TOOL_FUNCTION_STRICT", None)
            else:
                os.environ["AIA_TOOL_FUNCTION_STRICT"] = prev

    def test_apply_sets_strict_on_function_tools(self) -> None:
        tools = [
            {"type": "function", "function": {"name": "get_weather", "parameters": {"type": "object", "properties": {}}}},
            {"type": "not_function", "x": 1},
        ]
        out = _apply_strict_flag_to_function_tools(tools)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertTrue(out[0]["function"]["strict"])
        self.assertEqual(out[1].get("type"), "not_function")
        self.assertNotIn("strict", out[1])
        self.assertNotIn("strict", tools[0].get("function", {}))

    def test_apply_empty(self) -> None:
        self.assertEqual(_apply_strict_flag_to_function_tools([]), [])

    def test_apply_handles_missing_function_dict(self) -> None:
        out = _apply_strict_flag_to_function_tools([{"type": "function"}])
        assert out is not None
        self.assertEqual(out[0]["function"], {"strict": True})


if __name__ == "__main__":
    unittest.main()
