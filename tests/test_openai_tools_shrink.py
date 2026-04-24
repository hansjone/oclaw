from __future__ import annotations

import json
import unittest

from oclaw.platform.llm.chat_models import shrink_openai_tools_payload_for_api, _openai_tools_json_byte_length


class OpenAiToolsShrinkTests(unittest.TestCase):
    def test_shrink_fits_under_cap(self) -> None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "mcp__demo__ping",
                    "description": "x" * 2000,
                    "parameters": {
                        "type": "object",
                        "properties": {f"f{i}": {"type": "string", "description": "y" * 500} for i in range(40)},
                    },
                },
            }
        ]
        self.assertGreater(_openai_tools_json_byte_length(tools), 5000)
        out = shrink_openai_tools_payload_for_api(tools, max_json_bytes=4000)
        self.assertLessEqual(_openai_tools_json_byte_length(out), 4000)
        self.assertEqual(out[0]["function"]["name"], "mcp__demo__ping")
        self.assertEqual(out[0]["function"]["parameters"].get("type"), "object")


if __name__ == "__main__":
    unittest.main()
