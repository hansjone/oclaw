from __future__ import annotations

import time
from typing import Any

from svc.persistence.sqlite_store import SqliteStore


class ToolAuditAdapter:
    def __init__(self, store: SqliteStore):
        self.store = store

    def log_dispatch(
        self,
        *,
        session_id: str,
        specialist: str,
        task_kind: str,
        action: str,
        payload: dict[str, Any],
        status: str = "ok",
        reason: str = "",
    ) -> None:
        started = time.perf_counter()
        self.store.add_agent_audit_log(
            session_id=session_id,
            specialist=specialist,
            task_kind=task_kind,
            action=action,
            payload=payload,
            status=status,
            reason=reason,
            duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
        )
