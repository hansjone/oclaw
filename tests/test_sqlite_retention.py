from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from svc.persistence.sqlite_retention import prune_sqlite_retention
from svc.persistence.sqlite_store import SqliteStore


class SqliteRetentionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ret.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["AIA_ASSISTANT_DB_BACKEND"] = "sqlite"
        self.store = SqliteStore(str(self.db))
        self.sess = self.store.create_session("retention-test")
        self.session_id = str(self.sess.id)
        self.now = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
        self.old = (self.now - timedelta(days=40)).isoformat()
        self.fresh = (self.now - timedelta(days=2)).isoformat()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _seed(self) -> None:
        with self.store._connect() as conn:
            conn.execute(
                "INSERT INTO chat_message(session_id, role, content, timestamp) VALUES (?,?,?,?)",
                (self.session_id, "tool", "OLD_TOOL_PAYLOAD" * 100, self.old),
            )
            conn.execute(
                "INSERT INTO chat_message(session_id, role, content, timestamp) VALUES (?,?,?,?)",
                (self.session_id, "tool", "FRESH_TOOL", self.fresh),
            )
            conn.execute(
                "INSERT INTO chat_message(session_id, role, content, timestamp) VALUES (?,?,?,?)",
                (self.session_id, "assistant", "keep me", self.old),
            )
            conn.execute(
                "INSERT INTO tool_log(session_id, tool_name, specialist, args, result, timestamp) "
                "VALUES (?,?,?,?,?,?)",
                (self.session_id, "t1", "", "{}", '"OLD_RESULT"', self.old),
            )
            conn.execute(
                "INSERT INTO tool_log(session_id, tool_name, specialist, args, result, timestamp) "
                "VALUES (?,?,?,?,?,?)",
                (self.session_id, "t2", "", "{}", '"FRESH"', self.fresh),
            )
            conn.execute(
                "INSERT INTO trace_event(session_id, trace_id, span_id, parent_span_id, event_type, payload, timestamp) "
                "VALUES (?,?,?,?,?,?,?)",
                (self.session_id, "tr1", "sp1", "", "x", "{}", self.old),
            )
            conn.execute(
                "INSERT INTO channel_outbound_message"
                "(id, tenant_id, channel, account_id, chat_id, text, status, source, created_at, error) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("ob-old", "", "whatsapp", "wa", "c", "hi", "sent", "", self.old, ""),
            )
            conn.execute(
                "INSERT INTO channel_outbound_message"
                "(id, tenant_id, channel, account_id, chat_id, text, status, source, created_at, error) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("ob-pending", "", "whatsapp", "wa", "c", "hi", "pending", "", self.old, ""),
            )

    def test_dry_run_then_apply(self) -> None:
        self._seed()
        plan = prune_sqlite_retention(self.store, keep_days=30, dry_run=True, now=self.now)
        self.assertTrue(plan.get("ok"))
        self.assertTrue(plan.get("dry_run"))
        self.assertGreaterEqual(int(plan.get("total_rows") or 0), 3)
        self.assertGreater(int((plan.get("targets") or {}).get("chat_message_tool", {}).get("rows") or 0), 0)

        # Nothing deleted yet.
        with self.store._connect() as conn:
            n_tool = conn.execute(
                "SELECT COUNT(*) FROM chat_message WHERE role='tool'"
            ).fetchone()[0]
            self.assertEqual(int(n_tool), 2)

        out = prune_sqlite_retention(
            self.store,
            keep_days=30,
            dry_run=False,
            vacuum=False,
            now=self.now,
        )
        self.assertTrue(out.get("ok"))
        self.assertFalse(out.get("dry_run"))
        self.assertGreaterEqual(int(out.get("deleted_rows") or 0), 3)

        with self.store._connect() as conn:
            roles = [
                r[0]
                for r in conn.execute("SELECT role FROM chat_message ORDER BY id").fetchall()
            ]
            self.assertIn("assistant", roles)
            self.assertIn("tool", roles)  # fresh tool kept
            self.assertEqual(roles.count("tool"), 1)
            tool_logs = conn.execute("SELECT COUNT(*) FROM tool_log").fetchone()[0]
            self.assertEqual(int(tool_logs), 1)
            traces = conn.execute("SELECT COUNT(*) FROM trace_event").fetchone()[0]
            self.assertEqual(int(traces), 0)
            outbound = {
                r[0]: r[1]
                for r in conn.execute(
                    "SELECT id, status FROM channel_outbound_message"
                ).fetchall()
            }
            self.assertNotIn("ob-old", outbound)
            self.assertIn("ob-pending", outbound)

    def test_vacuum_shrinks_after_large_delete(self) -> None:
        self._seed()
        # Inflate then delete + vacuum.
        with self.store._connect() as conn:
            conn.execute(
                "INSERT INTO chat_message(session_id, role, content, timestamp) VALUES (?,?,?,?)",
                (self.session_id, "tool", "X" * 200_000, self.old),
            )
        before = self.db.stat().st_size
        out = prune_sqlite_retention(
            self.store,
            keep_days=30,
            dry_run=False,
            vacuum=True,
            now=self.now,
        )
        self.assertTrue(out.get("ok"))
        self.assertTrue((out.get("vacuum") or {}).get("ok"))
        after = self.db.stat().st_size
        self.assertLess(after, before)


if __name__ == "__main__":
    unittest.main()
