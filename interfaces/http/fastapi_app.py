from __future__ import annotations

import asyncio
import os
import shutil
from contextlib import asynccontextmanager
from typing import Any
import threading

from fastapi import FastAPI, WebSocket
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from oclaw.runtime.application.gateway import process_inbound_payload_usecase
from oclaw.interfaces.gateway.http_adapter import dispatch_gateway_http_method
from oclaw.interfaces.ws import ws_gateway_loop
from oclaw.interfaces.admin.routes import admin_static_dir, build_admin_router
from oclaw.runtime.agents.agent_scope import list_agent_ids, resolve_agent_workspace_dir, resolve_default_agent_id
from oclaw.interfaces.gateway.server_startup_plugins import prepare_gateway_plugin_bootstrap
from oclaw.runtime.hooks_runtime import (
    initialize_hooks_runtime,
    resolve_runtime_config,
    trigger_hook_event,
)
from oclaw.runtime.skills import skill_runtime_diagnostics
from oclaw.runtime.prompt_prebuild import run_runtime_prewarm
from oclaw.platform.config.paths import PROJECT_ROOT, db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.interfaces.http.weixin_ilink_api import router as weixin_ilink_router
from oclaw.runtime.workspaces.experts import warm_expert_workspace_cache


def _resolve_startup_workspace_dir(cfg: dict[str, Any]) -> str:
    try:
        default_agent_id = resolve_default_agent_id(cfg)
        ws = resolve_agent_workspace_dir(cfg, default_agent_id)
        ws_text = str(ws or "").strip()
        if ws_text and ws_text not in {".", "./"}:
            return ws_text
    except Exception:
        pass
    return str((PROJECT_ROOT / "runtime" / "workspaces" / "main").resolve())


def _resolve_startup_workspace_dirs(cfg: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen_ws: set[str] = set()
    try:
        agent_ids = list_agent_ids(cfg)
    except Exception:
        agent_ids = []
    if not agent_ids:
        agent_ids = [resolve_default_agent_id(cfg)]

    for aid in agent_ids:
        try:
            ws = str(resolve_agent_workspace_dir(cfg, aid) or "").strip()
        except Exception:
            ws = ""
        if not ws:
            continue
        key = ws.lower() if os.name == "nt" else ws
        if key in seen_ws:
            continue
        seen_ws.add(key)
        out.append((str(aid or "default"), ws))

    if out:
        return out
    return [("default", _resolve_startup_workspace_dir(cfg))]


def _relocate_root_scan_artifacts() -> None:
    """Keep generated scan artifacts out of repo root.

    Some helper scripts write scan snapshots to the current working directory.
    Normalize them into runtime/data/scan on gateway startup.
    """
    root = PROJECT_ROOT.resolve()
    target_dir = (PROJECT_ROOT / "runtime" / "data" / "scan").resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    patterns = ("history_entries_*.json", "state_scan_*.json")
    for pat in patterns:
        for src in root.glob(pat):
            try:
                if not src.is_file():
                    continue
                dst = target_dir / src.name
                if dst.exists():
                    # Keep newest artifact when both paths exist.
                    src_mtime = src.stat().st_mtime
                    dst_mtime = dst.stat().st_mtime
                    if src_mtime <= dst_mtime:
                        src.unlink(missing_ok=True)
                        continue
                    dst.unlink(missing_ok=True)
                shutil.move(str(src), str(dst))
            except Exception:
                continue


_PREWARM_SCHEDULER_LOCK = threading.Lock()
_PREWARM_SCHEDULER_RUNNING = False


def _prewarm_interval_seconds() -> int:
    raw = str(os.getenv("AIA_PREWARM_INTERVAL_SECONDS") or "").strip()
    if raw.isdigit():
        return max(60, min(int(raw), 86_400))
    return 600


def _spawn_periodic_prewarm_loop() -> None:
    global _PREWARM_SCHEDULER_RUNNING
    with _PREWARM_SCHEDULER_LOCK:
        if _PREWARM_SCHEDULER_RUNNING:
            return
        _PREWARM_SCHEDULER_RUNNING = True

    def _runner() -> None:
        global _PREWARM_SCHEDULER_RUNNING
        interval = _prewarm_interval_seconds()
        while True:
            try:
                out = run_runtime_prewarm(reason="scheduler")
                _ = out
            except Exception:
                pass
            time_to_sleep = max(30, interval)
            try:
                import time

                time.sleep(time_to_sleep)
            except Exception:
                break
        with _PREWARM_SCHEDULER_LOCK:
            _PREWARM_SCHEDULER_RUNNING = False

    th = threading.Thread(target=_runner, name="oclaw-prewarm-scheduler", daemon=True)
    th.start()


def _run_startup_hooks(app: FastAPI) -> None:
    def _log_info(message: str) -> None:
        print(message)

    def _log_warn(message: str) -> None:
        print(message)

    def _log_error(message: str) -> None:
        print(message)

    def _log_debug(message: str) -> None:
        _ = message

    # Force re-login after every gateway restart.
    try:
        revoked = SqliteStore(db_path()).revoke_all_auth_sessions()
        if revoked > 0:
            _log_info(f"[auth] revoked sessions on startup: {revoked}")
    except Exception as exc:
        _log_warn(f"[auth] failed to revoke sessions on startup: {exc}")

    try:
        cfg: dict[str, Any] = {}
        boot = prepare_gateway_plugin_bootstrap(
            cfg_at_start=cfg,
            startup_runtime_config=cfg,
            minimal_test_gateway=False,
            log={
                "info": _log_info,
                "warn": _log_warn,
                "error": _log_error,
                "debug": _log_debug,
            },
            core_gateway_handlers={},
            base_methods=[],
        )
        app.state.gateway_plugin_bootstrap = boot
    except Exception:
        app.state.gateway_plugin_bootstrap = None

    cfg = resolve_runtime_config()
    try:
        diag = skill_runtime_diagnostics()
        _log_info(f"[skills] root={diag.get('skills_root')} total={diag.get('skills_total')}")
    except Exception:
        pass
    try:
        warm_expert_workspace_cache()
    except Exception:
        pass
    try:
        prewarm = run_runtime_prewarm(reason="startup")
        _log_info(
            "[startup-prebuild] "
            f"ok={bool(prewarm.get('ok'))} "
            f"elapsed_ms={int(prewarm.get('elapsed_ms') or 0)} "
            f"freeze={bool(((prewarm.get('freeze') or {}).get('frozen')))}"
        )
    except Exception as exc:
        _log_warn(f"[startup-prebuild] failed: {exc}")
    try:
        _spawn_periodic_prewarm_loop()
        _log_info(f"[startup-prebuild] scheduler_started interval_s={_prewarm_interval_seconds()}")
    except Exception as exc:
        _log_warn(f"[startup-prebuild] scheduler_start_failed: {exc}")
    _relocate_root_scan_artifacts()
    startup_targets = _resolve_startup_workspace_dirs(cfg)
    initialize_hooks_runtime(cfg=cfg, workspace_dir=startup_targets[0][1])
    for agent_id, ws_dir in startup_targets:
        trigger_hook_event(
            event_type="gateway",
            action="startup",
            session_key=f"system:gateway:startup:{agent_id}",
            context={"cfg": cfg, "workspaceDir": ws_dir, "agentId": agent_id},
        )


@asynccontextmanager
async def _lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    _run_startup_hooks(app)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ops-gateway", version="0.1", lifespan=_lifespan)
    app.mount("/admin/assets", StaticFiles(directory=str(admin_static_dir())), name="admin-assets")
    app.include_router(build_admin_router())
    app.include_router(weixin_ilink_router)

    @app.middleware("http")
    async def _no_cache_for_admin_assets(request: Request, call_next):  # type: ignore[no-untyped-def]
        resp = await call_next(request)
        # Avoid stale JS/CSS after refactors (especially in Electron webview).
        # The admin SPA and /chat both load from /admin/assets/...
        if str(request.url.path or "").startswith("/admin/assets/"):
            resp.headers["Cache-Control"] = "no-store, max-age=0"
            resp.headers["Pragma"] = "no-cache"
        return resp

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"ok": "1"}

    @app.get("/chat", response_class=HTMLResponse)
    def chat_standalone() -> HTMLResponse:
        p = admin_static_dir() / "chat.html"
        return HTMLResponse(p.read_text(encoding="utf-8"))

    @app.post("/inbound")
    async def inbound(payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(process_inbound_payload_usecase, payload)

    @app.post("/inbound/{channel}")
    async def inbound_by_channel(channel: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload = payload if isinstance(payload, dict) else {}
        payload["channel"] = str(channel or "").strip().lower()
        return await asyncio.to_thread(process_inbound_payload_usecase, payload)

    @app.post("/wecom/inbound")
    async def wecom_inbound(payload: dict[str, Any]) -> dict[str, Any]:
        payload = payload if isinstance(payload, dict) else {}
        payload["channel"] = "wecom"
        return await asyncio.to_thread(process_inbound_payload_usecase, payload)

    @app.post("/gateway/method")
    async def gateway_method(payload: dict[str, Any]) -> dict[str, Any]:
        body = payload if isinstance(payload, dict) else {}
        method = str(body.get("method") or "").strip()
        params = body.get("params") if isinstance(body.get("params"), dict) else {}
        return await asyncio.to_thread(dispatch_gateway_http_method, method=method, params=params)

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws_gateway_loop(ws)

    return app


def main() -> int:
    host = (os.getenv("AIA_ASSISTANT_GATEWAY_HOST") or "0.0.0.0").strip()
    port = int(os.getenv("AIA_ASSISTANT_GATEWAY_PORT") or "8787")
    try:
        import uvicorn
    except Exception as exc:
        raise RuntimeError("missing dependency: uvicorn (pip install -r requirements.txt)") from exc
    uvicorn.run("oclaw.interfaces.http.fastapi_app:create_app", host=host, port=port, reload=False, factory=True)
    return 0


__all__ = ["create_app", "main", "_resolve_startup_workspace_dir", "_resolve_startup_workspace_dirs"]

