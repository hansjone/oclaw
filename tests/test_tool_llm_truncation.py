from __future__ import annotations

import json
import os
import tempfile
import unittest
import uuid
from unittest import mock

from runtime.chat.tool_runtime import (
    compact_turn_tool_messages_for_storage,
    tool_llm_message_max_chars,
    tool_persist_max_chars,
    truncate_tool_result_for_llm_messages,
)
from svc.persistence.sqlite_store import SqliteStore


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
        with mock.patch.dict(os.environ, {"AIA_TOOL_LLM_MESSAGE_MAX_CHARS": "9000"}, clear=False):
            self.assertEqual(tool_llm_message_max_chars(), 9000)

    def test_tool_persist_max_chars_default(self) -> None:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"AIA_TOOL_PERSIST_MAX_CHARS", "AIA_TOOL_LLM_MESSAGE_MAX_CHARS"}
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(tool_persist_max_chars(), 24_000)
            self.assertEqual(tool_llm_message_max_chars(), 0)

    def test_tool_persist_max_chars_disable(self) -> None:
        with mock.patch.dict(os.environ, {"AIA_TOOL_PERSIST_MAX_CHARS": "0"}, clear=False):
            self.assertEqual(tool_persist_max_chars(), 0)

    def test_compact_turn_defaults_to_persist_cap(self) -> None:
        """Post-turn compact runs with default 24k even when LLM wire cap is unlimited."""
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
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"AIA_TOOL_PERSIST_MAX_CHARS", "AIA_TOOL_LLM_MESSAGE_MAX_CHARS"}
        }
        with mock.patch.dict(os.environ, env, clear=True):
            stats = compact_turn_tool_messages_for_storage(
                store=store,
                session_id=sess.id,
                turn_uuid=turn_uuid,
            )
        self.assertEqual(int(stats.get("persist_cap") or 0), 24_000)
        self.assertGreaterEqual(int(stats.get("scanned") or 0), 1)
        self.assertGreaterEqual(int(stats.get("updated") or 0), 1)
        after = store.get_messages(session_id=sess.id, limit=20)
        after_tool = [m for m in after if m.id == row.id][0]
        self.assertIn("_truncated_for_llm", str(after_tool.content or ""))
        self.assertLess(len(str(after_tool.content or "")), 40_000)

    def test_compact_turn_can_be_disabled(self) -> None:
        db = f"{tempfile.gettempdir()}/oclaw-test-{uuid.uuid4().hex}.sqlite"
        store = SqliteStore(db)
        sess = store.create_session("t")
        turn_uuid = "turn-off"
        store.add_message(
            session_id=sess.id,
            role="tool",
            content=json.dumps({"ok": True, "blob": "x" * 50_000}, ensure_ascii=False),
            tool_calls={"tool_call_id": "c1", "name": "echo"},
            turn_uuid=turn_uuid,
        )
        with mock.patch.dict(os.environ, {"AIA_TOOL_PERSIST_MAX_CHARS": "0"}, clear=False):
            stats = compact_turn_tool_messages_for_storage(
                store=store,
                session_id=sess.id,
                turn_uuid=turn_uuid,
            )
        self.assertEqual(int(stats.get("skipped") or 0), 1)
        self.assertEqual(int(stats.get("updated") or 0), 0)

    def test_tool_log_default_cap(self) -> None:
        db = f"{tempfile.gettempdir()}/oclaw-test-{uuid.uuid4().hex}.sqlite"
        store = SqliteStore(db)
        sess = store.create_session("t")
        env = {k: v for k, v in os.environ.items() if k != "AIA_TOOL_LOG_MAX_CHARS"}
        with mock.patch.dict(os.environ, env, clear=True):
            store.add_tool_log(
                session_id=sess.id,
                tool_name="echo",
                args={},
                result={"ok": True, "blob": "y" * 200_000},
            )
        logs = store.get_tool_logs(sess.id, limit=5)
        self.assertEqual(len(logs), 1)
        blob = json.dumps(logs[0]["result"], ensure_ascii=False)
        self.assertLessEqual(len(blob), 70_000)
        self.assertTrue(logs[0]["result"].get("ok") is True)


if __name__ == "__main__":
    unittest.main()
