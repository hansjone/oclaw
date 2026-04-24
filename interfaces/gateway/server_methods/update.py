from __future__ import annotations

import time
from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _ok(respond, payload: Any) -> None:
    if callable(respond):
        respond(True, payload, None, None)


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _norm_str(v: Any) -> str | None:
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return None


def _as_int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    return None


def _parse_restart_request_params(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "sessionKey": _norm_str(params.get("sessionKey")),
        "deliveryContext": params.get("deliveryContext") if isinstance(params.get("deliveryContext"), dict) else None,
        "threadId": _norm_str(params.get("threadId")),
        "note": _norm_str(params.get("note")),
        "restartDelayMs": max(0, _as_int(params.get("restartDelayMs")) or 0) or None,
    }


def _update_run_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params")
    respond = opts.get("respond")
    context = opts.get("context")
    client = opts.get("client")
    if params is not None and not isinstance(params, dict):
        _bad(respond, "invalid update.run params")
        return
    p = dict(params or {})

    parsed = _parse_restart_request_params(p)
    timeout_ms_raw = _as_int(p.get("timeoutMs"))
    timeout_ms = max(1000, timeout_ms_raw) if isinstance(timeout_ms_raw, int) else None

    runner = context.get("run_gateway_update") if isinstance(context, dict) else None
    if callable(runner):
        try:
            result = runner({"timeoutMs": timeout_ms, "params": p})
            if not isinstance(result, dict):
                result = {
                    "status": "ok",
                    "mode": "unknown",
                    "steps": [],
                    "durationMs": 0,
                }
        except Exception as exc:
            result = {
                "status": "error",
                "mode": "unknown",
                "reason": str(exc),
                "steps": [],
                "durationMs": 0,
            }
    else:
        result = {
            "status": "ok",
            "mode": "staging",
            "steps": [],
            "durationMs": 0,
        }

    payload = {
        "kind": "update",
        "status": result.get("status"),
        "ts": int(time.time() * 1000),
        "sessionKey": parsed["sessionKey"],
        "deliveryContext": parsed["deliveryContext"],
        "threadId": parsed["threadId"],
        "message": parsed["note"],
        "doctorHint": "Run doctor in non-interactive mode if needed.",
        "stats": {
            "mode": result.get("mode"),
            "root": result.get("root"),
            "before": result.get("before"),
            "after": result.get("after"),
            "steps": result.get("steps") if isinstance(result.get("steps"), list) else [],
            "reason": result.get("reason"),
            "durationMs": result.get("durationMs"),
        },
    }

    sentinel_path = None
    write_sentinel = context.get("write_restart_sentinel") if isinstance(context, dict) else None
    if callable(write_sentinel):
        try:
            sentinel_path = write_sentinel(payload)
        except Exception:
            sentinel_path = None

    restart = None
    if result.get("status") == "ok":
        schedule = context.get("schedule_gateway_restart") if isinstance(context, dict) else None
        if callable(schedule):
            actor = {"actor": "unknown", "deviceId": None, "clientIp": None}
            if isinstance(client, dict):
                connect = client.get("connect")
                if isinstance(connect, dict):
                    actor["deviceId"] = connect.get("device", {}).get("id") if isinstance(connect.get("device"), dict) else None
                actor["clientIp"] = client.get("client_ip")
            restart = schedule(
                {
                    "delayMs": parsed["restartDelayMs"],
                    "reason": "update.run",
                    "audit": {"actor": actor.get("actor"), "deviceId": actor.get("deviceId"), "clientIp": actor.get("clientIp"), "changedPaths": []},
                }
            )
        else:
            restart = {"scheduled": True, "reason": "update.run", "delayMs": parsed["restartDelayMs"]}

    _ok(
        respond,
        {
            "ok": result.get("status") != "error",
            "result": result,
            "restart": restart,
            "sentinel": {"path": sentinel_path, "payload": payload},
        },
    )


update_handlers: GatewayRequestHandlers = {
    "update.run": _update_run_handler,
}

