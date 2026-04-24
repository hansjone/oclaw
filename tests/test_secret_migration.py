from __future__ import annotations

import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path

from oclaw.platform.persistence.sqlite_store import SqliteStore


class SecretMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ops.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["OPS_ASSISTANT_MASTER_KEY"] = "unit-test-master-key"
        self.store = SqliteStore(str(self.db))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_migrate_b64_secrets_to_fernet_is_idempotent(self) -> None:
        # Insert legacy b64 secret into app_setting
        plain1 = "secret-one"
        enc1 = "b64:" + base64.b64encode(plain1.encode("utf-8")).decode("ascii")
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_setting (key, value, is_secret, updated_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, is_secret = 1, updated_at = excluded.updated_at
                """,
                ("legacy1", enc1, "2026-01-01T00:00:00+00:00"),
            )

        # Insert legacy b64 secret into llm_profile.api_key
        pid = self.store.create_llm_profile(name="p1", mode="openai", model="gpt-4o-mini", base_url=None, owner_user_id=None)
        plain2 = "sk-test-123"
        enc2 = "b64:" + base64.b64encode(plain2.encode("utf-8")).decode("ascii")
        with self.store._connect() as conn:
            conn.execute("UPDATE llm_profile SET api_key = ? WHERE id = ?", (enc2, pid))

        res1 = self.store.migrate_secrets_to_fernet()
        self.assertEqual(int(res1.get("migrated_app_settings") or 0), 1)
        self.assertEqual(int(res1.get("migrated_llm_profiles") or 0), 1)

        # Ensure underlying storage no longer uses b64: (dpapi on Windows, fernet elsewhere)
        with self.store._connect() as conn:
            row = conn.execute("SELECT value FROM app_setting WHERE key = ? AND is_secret = 1", ("legacy1",)).fetchone()
            self.assertIsNotNone(row)
            val = str(row["value"] or "")
            self.assertFalse(val.startswith("b64:"))
            if sys.platform == "win32":
                self.assertTrue(val.startswith("dpapi:") or val.startswith("fernet:"))
            else:
                self.assertTrue(val.startswith("fernet:"))

        # Values should still be readable
        self.assertEqual(self.store.get_secret("legacy1"), plain1)
        self.assertEqual(self.store.get_llm_profile_secret(pid), plain2)

        # Second run should migrate nothing
        res2 = self.store.migrate_secrets_to_fernet()
        self.assertEqual(int(res2.get("migrated_app_settings") or 0), 0)
        self.assertEqual(int(res2.get("migrated_llm_profiles") or 0), 0)


if __name__ == "__main__":
    unittest.main()

