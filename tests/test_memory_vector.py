from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.orchestration.memory import maybe_write_turn_memory, semantic_retrieve
from svc.persistence.sqlite_store import SqliteStore


class MemoryVectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(self._tmp.name) / "test.sqlite"
        self.store = SqliteStore(str(db))
        self.store.set_setting("MEMORY_VECTOR_ENABLED", "1")
        self.store.set_setting("MEMORY_VECTOR_BACKEND", "sqlite")
        self.store.set_setting("MEMORY_WRITE_ENABLED", "1")
        self.store.set_setting("MEMORY_WRITE_MIN_CONFIDENCE", "0.5")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_write_and_semantic_retrieve_same_tenant_user(self) -> None:
        res = maybe_write_turn_memory(
            self.store,
            tenant_id="t1",
            user_id="u1",
            session_id="s1",
            user_text="记住我喜欢喝黑咖啡，不加糖。",
            assistant_text="好的，我记住了你的偏好。",
        )
        self.assertTrue(res.get("ok"))
        hits = semantic_retrieve(
            self.store,
            query="我喝什么咖啡",
            tenant_id="t1",
            user_id="u1",
            session_id="s2",
            top_k=3,
        )
        self.assertGreaterEqual(len(hits), 1)

    def test_tenant_isolation(self) -> None:
        maybe_write_turn_memory(
            self.store,
            tenant_id="tA",
            user_id="uA",
            session_id="sA",
            user_text="记住我的常住城市是上海。",
            assistant_text="已记录。",
        )
        hits = semantic_retrieve(
            self.store,
            query="我的城市",
            tenant_id="tB",
            user_id="uA",
            session_id="sB",
            top_k=3,
        )
        self.assertEqual(hits, [])

    def test_vector_disabled_fallback(self) -> None:
        self.store.set_setting("MEMORY_VECTOR_ENABLED", "0")
        hits = semantic_retrieve(
            self.store,
            query="anything",
            tenant_id="t1",
            user_id="u1",
            top_k=3,
        )
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
