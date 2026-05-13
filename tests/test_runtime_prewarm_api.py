from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from interfaces.admin import routes as routes_mod


def test_runtime_prewarm_routes_registered_and_guarded() -> None:
    app = FastAPI()
    app.include_router(routes_mod.build_admin_router())
    client = TestClient(app, raise_server_exceptions=False)
    paths = set(app.openapi().get("paths", {}).keys())
    assert "/admin/api/runtime/prewarm" in paths
    assert "/admin/api/runtime/prewarm/status" in paths
    assert "/admin/api/runtime/prewarm/prompts" in paths

    r1 = client.get("/admin/api/runtime/prewarm/status")
    r2 = client.post("/admin/api/runtime/prewarm", json={"mode": "sync", "reason": "test"})
    r3 = client.get("/admin/api/runtime/prewarm/prompts")
    assert r1.status_code == 401
    assert r2.status_code == 401
    assert r3.status_code == 401
