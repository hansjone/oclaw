from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from interfaces.gateway.http_adapter import dispatch_gateway_http_method
from svc.persistence.assistant_store import reset_assistant_store_singleton
from svc.persistence.sqlite_store import SqliteStore


class GatewayCronServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "cron.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["AIA_ASSISTANT_DB_BACKEND"] = "sqlite"
        reset_assistant_store_singleton()
        self.store = SqliteStore(str(self.db))
        t = self.store.create_tenant("default")
        self.tenant_id = str(t["id"])

    def tearDown(self) -> None:
        reset_assistant_store_singleton()
        self._tmp.cleanup()

    def test_cron_add_and_list(self) -> None:
        once_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        add = dispatch_gateway_http_method(
            "cron.add",
            {
                "name": "gw job",
                "schedule": once_at,
                "schedule_kind": "once",
                "tenant_id": self.tenant_id,
                "prompt": "hello",
            },
        )
        self.assertTrue(add.get("ok"), add)
        lst = dispatch_gateway_http_method("cron.list", {"tenant_id": self.tenant_id})
        self.assertTrue(lst.get("ok"), lst)
        payload = lst.get("payload") or {}
        self.assertGreaterEqual(len(payload.get("items") or []), 1)


if __name__ == "__main__":
    unittest.main()
