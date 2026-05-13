"""_init_db prunes rows that reference deleted chat_session (legacy FK-off deletes)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from svc.persistence.sqlite_store import SqliteStore


class SessionOrphanPruneTests(unittest.TestCase):
    def test_chat_message_pruned_after_session_deleted_with_fk_off(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "x.sqlite"
            s = SqliteStore(str(db))
            sess = s.create_session("t")
            s.add_message(sess.id, "user", "hello")
            raw = sqlite3.connect(str(db))
            raw.execute("PRAGMA foreign_keys=OFF")
            raw.execute("DELETE FROM chat_session WHERE id = ?", (sess.id,))
            raw.commit()
            raw.close()
            self.assertGreater(
                int(
                    sqlite3.connect(str(db))
                    .execute("select count(*) from chat_message where session_id = ?", (sess.id,))
                    .fetchone()[0]
                ),
                0,
            )
            SqliteStore(str(db))
            n = int(
                sqlite3.connect(str(db))
                .execute("select count(*) from chat_message where session_id = ?", (sess.id,))
                .fetchone()[0]
            )
            self.assertEqual(n, 0)

    def test_oclaw_task_pruned_when_session_row_missing(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "y.sqlite"
            store = SqliteStore(str(db))
            sess = store.create_session("s")
            with store._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO oclaw_task(
                        id, tenant_id, session_id, status, payload, result,
                        attempt_count, last_error, created_at, updated_at
                    ) VALUES (?, ?, ?, 'done', '{}', '{}', 0, '', datetime('now'), datetime('now'))
                    """,
                    ("task-1", "tenant-1", sess.id),
                )
            raw = sqlite3.connect(str(db))
            raw.execute("PRAGMA foreign_keys=OFF")
            raw.execute("DELETE FROM chat_session WHERE id = ?", (sess.id,))
            raw.commit()
            raw.close()
            SqliteStore(str(db))
            c = int(sqlite3.connect(str(db)).execute("select count(*) from oclaw_task").fetchone()[0])
            self.assertEqual(c, 0)


if __name__ == "__main__":
    unittest.main()
