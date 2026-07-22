from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from interfaces.admin.chat_api import include_chat_routes
from svc.jobs.background_jobs import BackgroundJobStore


def test_chat_jobs_api_list_cancel_purge(tmp_path, monkeypatch) -> None:
    store = BackgroundJobStore(root_dir=tmp_path / "jobs")
    monkeypatch.setattr("svc.jobs.background_jobs.get_job_store", lambda root_dir=None: store)
    # Also patch the import site used inside route handlers
    import svc.jobs.background_jobs as bj

    monkeypatch.setattr(bj, "get_job_store", lambda root_dir=None: store)

    class _FakeSqlite:
        pass

    def _resolve_auth(_store, _auth):
        return {"tenant_id": "t1", "user_id": "u1", "username": "u1"}

    monkeypatch.setattr("interfaces.admin.chat_api.get_assistant_store", lambda: _FakeSqlite())

    app = FastAPI()
    from fastapi import APIRouter

    router = APIRouter()
    include_chat_routes(router, resolve_auth=_resolve_auth)
    app.include_router(router)
    client = TestClient(app)

    started = store.start(command="echo hi", cwd=str(tmp_path), timeout_s=5, name="ui-job")
    assert started.get("ok") is True
    job_id = started["job_id"]

    r = client.get("/admin/api/chat/jobs", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert any(j.get("job_id") == job_id for j in body.get("jobs") or [])

    # wait finish then purge
    import time

    deadline = time.time() + 8
    while time.time() < deadline:
        g = store.get(job_id)
        if g.get("done"):
            break
        time.sleep(0.05)
    assert store.get(job_id).get("done") is True

    d = client.delete(f"/admin/api/chat/jobs/{job_id}", headers={"Authorization": "Bearer x"})
    assert d.status_code == 200
    assert d.json().get("purged") is True
