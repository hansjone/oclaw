from __future__ import annotations

from pathlib import Path

from oclaw.platform.persistence.sqlite_store import SqliteStore


def test_openclaw_task_status_flow(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "task.sqlite"))
    task = store.openclaw_task_create(
        tenant_id="tenant-a",
        session_id="session-a",
        payload={"text": "hello"},
    )
    assert task.status == "queued"

    claimed = store.openclaw_task_claim(worker_id="worker-1")
    assert claimed is not None
    assert claimed.id == task.id
    assert claimed.status == "claimed"
    assert claimed.claimed_by == "worker-1"
    assert claimed.attempt_count >= 1

    ok = store.openclaw_task_finish(task_id=task.id, result={"reply_text": "done"})
    assert ok
    done = store.openclaw_task_get(task_id=task.id)
    assert done is not None
    assert done.status == "done"
    assert "done" in done.result

