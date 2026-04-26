from __future__ import annotations

import json
import unittest

from oclaw.runtime.chat.tool_runtime import (
    compact_turn_tool_messages_for_storage,
    tool_llm_message_max_chars,
    truncate_tool_result_for_llm_messages,
)
from oclaw.platform.persistence.sqlite_store import SqliteStore


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

    def test_compact_turn_tool_messages_for_storage(self) -> None:
        import tempfile
        import uuid

        db = f"{tempfile.gettempdir()}/oclaw-test-{uuid.uuid4().hex}.sqlite"
        store = SqliteStore(db)
        sess = store.create_session("t")
        turn_uuid = "turn-1"
        store.add_message(
            session_id=sess.id,
            role="assistant",
            content="",
            tool_calls=[{"id": "c1", "name": "echo", "arguments": {"x": 1}}],
            turn_uuid=turn_uuid,
        )
        huge = "x" * 200_000
        row = store.add_message(
            session_id=sess.id,
            role="tool",
            content=json.dumps({"ok": True, "blob": huge}, ensure_ascii=False),
            tool_calls={"tool_call_id": "c1", "name": "echo", "assistant_message_id": 1},
            turn_uuid=turn_uuid,
        )
        before = store.get_messages(session_id=sess.id, limit=20)
        before_tool = [m for m in before if m.id == row.id][0]
        self.assertNotIn("_truncated_for_llm", str(before_tool.content or ""))
        from unittest import mock

        with mock.patch.dict("os.environ", {"AIA_TOOL_LLM_MESSAGE_MAX_CHARS": "8000"}, clear=False):
            stats = compact_turn_tool_messages_for_storage(
                store=store,
                session_id=sess.id,
                turn_uuid=turn_uuid,
            )
        self.assertGreaterEqual(int(stats.get("scanned") or 0), 1)
        self.assertGreaterEqual(int(stats.get("updated") or 0), 1)
        after = store.get_messages(session_id=sess.id, limit=20)
        after_tool = [m for m in after if m.id == row.id][0]
        self.assertIn("_truncated_for_llm", str(after_tool.content or ""))


if __name__ == "__main__":
    unittest.main()
