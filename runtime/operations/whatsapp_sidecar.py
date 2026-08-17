"""WhatsApp Baileys sidecar control helpers for admin / ops."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from runtime.operations.runtime import is_pid_running
from svc.config.log_paths import oclaw_log_root
from svc.config.paths import PROJECT_ROOT

DEFAULT_CHANNEL_ID = "whatsapp"
DEFAULT_ACCOUNT_ID = "wa-default"
DEFAULT_GATEWAY_BASE_URL = "http://127.0.0.1:8787"


def sidecar_root(channel_id: str = DEFAULT_CHANNEL_ID) -> Path:
    cid = str(channel_id or DEFAULT_CHANNEL_ID).strip() or DEFAULT_CHANNEL_ID
    return (PROJECT_ROOT / "data" / "channel_sidecar" / cid).resolve()


def state_dir(channel_id: str = DEFAULT_CHANNEL_ID) -> Path:
    return sidecar_root(channel_id) / "state"


def auth_dir(channel_id: str = DEFAULT_CHANNEL_ID) -> Path:
    return state_dir(channel_id) / "auth"


def pid_file(channel_id: str = DEFAULT_CHANNEL_ID) -> Path:
    return sidecar_root(channel_id) / "pid.txt"


def bridge_status_file(channel_id: str = DEFAULT_CHANNEL_ID) -> Path:
    return state_dir(channel_id) / "bridge_status.json"


def scripts_dir() -> Path:
    return (PROJECT_ROOT / "runtime" / "operations" / "scripts").resolve()


def bridge_src_dir() -> Path:
    return (PROJECT_ROOT / "runtime" / "operations" / "whatsapp_bridge").resolve()


def _read_pid(channel_id: str = DEFAULT_CHANNEL_ID) -> int:
    p = pid_file(channel_id)
    if not p.exists():
        return 0
    try:
        raw = (p.read_text(encoding="utf-8", errors="replace").strip().splitlines() or [""])[0].strip()
        return int(raw) if raw.isdigit() else 0
    except Exception:
        return 0


def _write_local_status(channel_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    path = bridge_status_file(channel_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    prev: dict[str, Any] = {}
    if path.exists():
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                prev = obj
        except Exception:
            prev = {}
    next_obj = dict(prev)
    next_obj.update(patch or {})
    next_obj["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path.write_text(json.dumps(next_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return next_obj


def _read_bridge_status(channel_id: str = DEFAULT_CHANNEL_ID) -> dict[str, Any]:
    path = bridge_status_file(channel_id)
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _read_bound_me(channel_id: str = DEFAULT_CHANNEL_ID) -> dict[str, str]:
    creds = auth_dir(channel_id) / "creds.json"
    if not creds.exists():
        return {"me": "", "phone": "", "name": ""}
    try:
        obj = json.loads(creds.read_text(encoding="utf-8"))
    except Exception:
        return {"me": "", "phone": "", "name": ""}
    me_obj = obj.get("me") if isinstance(obj, dict) else None
    if not isinstance(me_obj, dict):
        return {"me": "", "phone": "", "name": ""}
    me = str(me_obj.get("id") or "").strip()
    name = str(me_obj.get("name") or "").strip()
    phone = me.split("@")[0].split(":")[0]
    phone = "".join(ch for ch in phone if ch.isdigit())
    return {"me": me, "phone": phone, "name": name}


def _sync_bridge_sources(channel_id: str = DEFAULT_CHANNEL_ID) -> None:
    root = sidecar_root(channel_id)
    src = bridge_src_dir()
    if not src.exists() or not root.exists():
        return
    for name in ("baileys_runner.ts", "auth.ts", "qr.ts", "status.ts"):
        sp = src / name
        if sp.exists():
            shutil.copy2(sp, root / name)


def _run_ps1(script_name: str, args: list[str] | None = None, *, timeout_s: float = 120.0) -> dict[str, Any]:
    script = scripts_dir() / script_name
    if not script.exists():
        return {"ok": False, "error": f"script_missing:{script_name}"}
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        *(args or []),
    ]
    try:
        cp = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(5.0, float(timeout_s)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "error": "timeout",
            "stdout": str(exc.stdout or ""),
            "stderr": str(exc.stderr or ""),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    out = (cp.stdout or "").strip()
    err = (cp.stderr or "").strip()
    return {
        "ok": int(cp.returncode or 0) == 0,
        "returncode": int(cp.returncode or 0),
        "stdout": out[-4000:],
        "stderr": err[-4000:],
        "error": "" if int(cp.returncode or 0) == 0 else (err or out or f"exit_{cp.returncode}"),
    }


def installed(channel_id: str = DEFAULT_CHANNEL_ID) -> bool:
    return (sidecar_root(channel_id) / "baileys_runner.ts").exists()


def _needs_rebind_disconnect(bridge: dict[str, Any]) -> bool:
    code = bridge.get("last_disconnect_status")
    try:
        n = int(code) if code is not None else None
    except (TypeError, ValueError):
        n = None
    if n in (403, 405, 500):
        return True
    err = str(bridge.get("last_error") or "").lower()
    return n == 405 and "connection failure" in err


def _qr_to_data_url(qr_text: str) -> str:
    text = str(qr_text or "").strip()
    if not text:
        return ""
    try:
        import base64
        import io

        import qrcode

        img = qrcode.make(text)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def session_status(
    *,
    channel_id: str = DEFAULT_CHANNEL_ID,
    account_id: str = DEFAULT_ACCOUNT_ID,
    gateway_base_url: str = DEFAULT_GATEWAY_BASE_URL,
) -> dict[str, Any]:
    cid = str(channel_id or DEFAULT_CHANNEL_ID).strip() or DEFAULT_CHANNEL_ID
    aid = str(account_id or os.getenv("AIA_WHATSAPP_ACCOUNT_ID") or DEFAULT_ACCOUNT_ID).strip() or DEFAULT_ACCOUNT_ID
    pid = _read_pid(cid)
    running = bool(pid and is_pid_running(pid))
    bound_info = _read_bound_me(cid)
    bridge = _read_bridge_status(cid)
    auth_exists = auth_dir(cid).exists() and any(auth_dir(cid).glob("*.json"))
    bound = bool(bound_info.get("me") or auth_exists)
    connection = str(bridge.get("connection") or "").strip().lower()
    if not running:
        if bound:
            lifecycle = "bound_stopped"
        else:
            lifecycle = "unbound"
        connection = "stopped"
    else:
        if connection == "open":
            lifecycle = "online"
        elif connection == "qr":
            lifecycle = "awaiting_scan"
        elif connection == "connecting":
            lifecycle = "connecting"
        elif connection == "logged_out":
            lifecycle = "logged_out"
        elif connection == "needs_rebind" or _needs_rebind_disconnect(bridge):
            lifecycle = "needs_rebind"
        elif bound:
            lifecycle = "bound_offline"
            if not connection:
                connection = "close"
        else:
            lifecycle = "connecting"
            if not connection:
                connection = "connecting"
    me = str(bridge.get("me") or bound_info.get("me") or "").strip()
    phone = str(bridge.get("phone") or bound_info.get("phone") or "").strip()
    name = str(bound_info.get("name") or "").strip()
    qr = str(bridge.get("qr") or "").strip()
    qr_data_url = str(bridge.get("qr_data_url") or "").strip()
    qr_png_name = str(bridge.get("qr_png") or "").strip()
    qr_png_path = state_dir(cid) / qr_png_name if qr_png_name else state_dir(cid) / "qr.png"
    if (not qr_data_url) and qr_png_path.exists():
        try:
            import base64

            raw = qr_png_path.read_bytes()
            qr_data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
        except Exception:
            qr_data_url = ""
    if (not qr_data_url) and qr:
        qr_data_url = _qr_to_data_url(qr)
    stale_qr = False
    if qr or qr_data_url:
        try:
            updated = str(bridge.get("updated_at") or "").strip()
            if updated:
                # QR older than 2 minutes is usually expired.
                from datetime import datetime, timezone

                ts = datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp()
                stale_qr = (time.time() - ts) > 120
        except Exception:
            stale_qr = False
    log_path = oclaw_log_root() / "whatsapp_sidecar.log"
    return {
        "ok": True,
        "channel_id": cid,
        "account_id": aid,
        "gateway_base_url": str(gateway_base_url or DEFAULT_GATEWAY_BASE_URL).rstrip("/"),
        "installed": installed(cid),
        "sidecar_running": running,
        "pid": int(pid or 0) if running else 0,
        "bound": bound,
        "lifecycle": lifecycle,
        "connection": connection or ("stopped" if not running else "unknown"),
        "me": me,
        "phone": phone,
        "display_name": name,
        "qr": qr if lifecycle == "awaiting_scan" else "",
        "qr_data_url": qr_data_url if lifecycle == "awaiting_scan" else "",
        "qr_stale": bool(stale_qr) if lifecycle == "awaiting_scan" else False,
        "last_disconnect_reason": str(bridge.get("last_disconnect_reason") or ""),
        "last_disconnect_status": bridge.get("last_disconnect_status"),
        "last_error": str(bridge.get("last_error") or ""),
        "reconnect_attempt": int(bridge.get("reconnect_attempt") or 0),
        "bridge_updated_at": str(bridge.get("updated_at") or ""),
        "auth_dir": str(auth_dir(cid)),
        "log_path": str(log_path),
        "status_hint": {
            "unbound": "not_bound",
            "bound_stopped": "bound_but_sidecar_stopped",
            "bound_offline": "bound_but_offline",
            "online": "online",
            "awaiting_scan": "scan_qr",
            "logged_out": "logged_out_need_rebind",
            "needs_rebind": "session_invalid_need_rebind",
            "connecting": "connecting",
        }.get(lifecycle, lifecycle),
    }


def stop_sidecar(channel_id: str = DEFAULT_CHANNEL_ID, *, force: bool = True) -> dict[str, Any]:
    cid = str(channel_id or DEFAULT_CHANNEL_ID).strip() or DEFAULT_CHANNEL_ID
    args = ["-ChannelId", cid]
    if force:
        args.append("-Force")
    result = _run_ps1("whatsapp_stop.ps1", args, timeout_s=60.0)
    _write_local_status(
        cid,
        {
            "connection": "stopped",
            "qr": "",
            "qr_data_url": "",
            "qr_png": "",
            "last_error": "",
            "reconnect_attempt": 0,
        },
    )
    return {"ok": bool(result.get("ok")), "action": "stop", **result}


def start_sidecar(
    channel_id: str = DEFAULT_CHANNEL_ID,
    *,
    gateway_base_url: str = DEFAULT_GATEWAY_BASE_URL,
) -> dict[str, Any]:
    cid = str(channel_id or DEFAULT_CHANNEL_ID).strip() or DEFAULT_CHANNEL_ID
    if not installed(cid):
        return {"ok": False, "error": "whatsapp_sidecar_not_installed", "action": "start"}
    _sync_bridge_sources(cid)
    # Avoid duplicate processes.
    cur = session_status(channel_id=cid, gateway_base_url=gateway_base_url)
    if cur.get("sidecar_running"):
        return {"ok": True, "action": "start", "already_running": True, "status": cur}
    base = str(gateway_base_url or DEFAULT_GATEWAY_BASE_URL).rstrip("/") or DEFAULT_GATEWAY_BASE_URL
    result = _run_ps1(
        "whatsapp_start.ps1",
        ["-ChannelId", cid, "-GatewayBaseUrl", base],
        timeout_s=90.0,
    )
    # Give runner a moment to write status.
    time.sleep(1.0)
    status = session_status(channel_id=cid, gateway_base_url=base)
    return {"ok": bool(result.get("ok")), "action": "start", "status": status, **result}


def unbind_session(
    channel_id: str = DEFAULT_CHANNEL_ID,
    *,
    gateway_base_url: str = DEFAULT_GATEWAY_BASE_URL,
) -> dict[str, Any]:
    """Stop sidecar and clear device auth so a fresh QR bind is required."""
    cid = str(channel_id or DEFAULT_CHANNEL_ID).strip() or DEFAULT_CHANNEL_ID
    stop = stop_sidecar(cid, force=True)
    auth = auth_dir(cid)
    removed_auth = False
    if auth.exists():
        shutil.rmtree(auth, ignore_errors=True)
        removed_auth = not auth.exists()
    for extra in (state_dir(cid) / "qr.png", bridge_status_file(cid)):
        try:
            if extra.exists():
                extra.unlink()
        except Exception:
            pass
    _write_local_status(
        cid,
        {
            "connection": "stopped",
            "me": "",
            "phone": "",
            "qr": "",
            "qr_data_url": "",
            "qr_png": "",
            "last_disconnect_reason": "",
            "last_disconnect_status": None,
            "last_error": "",
            "reconnect_attempt": 0,
        },
    )
    status = session_status(channel_id=cid, gateway_base_url=gateway_base_url)
    return {
        "ok": True,
        "action": "unbind",
        "removed_auth": removed_auth,
        "stop": stop,
        "status": status,
    }


def start_bind(
    channel_id: str = DEFAULT_CHANNEL_ID,
    *,
    gateway_base_url: str = DEFAULT_GATEWAY_BASE_URL,
    clear_auth: bool = False,
) -> dict[str, Any]:
    """Ensure sidecar is running so a QR can appear (optionally after clearing auth)."""
    cid = str(channel_id or DEFAULT_CHANNEL_ID).strip() or DEFAULT_CHANNEL_ID
    base = str(gateway_base_url or DEFAULT_GATEWAY_BASE_URL).rstrip("/") or DEFAULT_GATEWAY_BASE_URL
    if clear_auth:
        unbind_session(cid, gateway_base_url=base)
    else:
        stop_sidecar(cid, force=True)
    started = start_sidecar(cid, gateway_base_url=base)
    # Poll for QR / online (fresh sidecar may take 10-40s to emit QR).
    status = started.get("status") if isinstance(started.get("status"), dict) else session_status(channel_id=cid, gateway_base_url=base)
    for _ in range(45):
        life = str(status.get("lifecycle") or "")
        if life == "online":
            break
        if life == "awaiting_scan" and (status.get("qr_data_url") or status.get("qr")):
            break
        time.sleep(1.0)
        status = session_status(channel_id=cid, gateway_base_url=base)
    return {
        "ok": bool(started.get("ok")),
        "action": "bind",
        "clear_auth": bool(clear_auth),
        "start": started,
        "status": status,
    }
