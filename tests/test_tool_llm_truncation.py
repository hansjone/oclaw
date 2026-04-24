from __future__ import annotations

import json
import unittest

from oclaw.runtime.chat.tool_runtime import truncate_tool_result_for_llm_messages, tool_llm_message_max_chars


class ToolLlmTruncationTests(unittest.TestCase):
    def test_small_payload_unchanged(self) -> None:
        d = {"ok": True, "files": ["a.txt", "b.txt"], "count": 2}
        self.assertEqual(truncate_tool_result_for_llm_messages(d), d)

    def test_huge_files_truncated(self) -> None:
        cap = 8000
        files = [f"f{i:05d}.txt" for i in range(5000)]
        d = {"ok": True, "files": files, "root": "C:\\\\test"}
        out = truncate_tool_result_for_llm_messages(d, max_chars=cap)
        self.assertTrue(out.get("_truncated_for_llm"))
        self.assertLessEqual(len(json.dumps(out, ensure_ascii=False)), cap)
        self.assertIn("files_total", out)
        self.assertGreater(out["files_total"], len(out.get("files") or []))

    def test_tool_llm_max_chars_env(self) -> None:
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"AIA_TOOL_LLM_MESSAGE_MAX_CHARS": "9000"}, clear=False):
            self.assertEqual(tool_llm_message_max_chars(), 9000)


if __name__ == "__main__":
    unittest.main()
