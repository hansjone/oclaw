from __future__ import annotations

from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape

DEVICE_TOKEN_ROTATION_DENIED_MESSAGE = "device token rotation denied"


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


def _caller_scopes(client: Any) -> list[str]:
    if not isinstance(client, dict):
        return []
    connect = client.get("connect")
    if not isinstance(connect, dict):
        return []
    scopes = connect.get("scopes")
    if isinstance(scopes, list):
        return [str(x) for x in scopes if isinstance(x, str)]
    return []


def _caller_device_id(client: Any) -> str | None:
    if not isinstance(client, dict):
        return None
    connect = client.get("connect")
    if not isinstance(connect, dict):
        return None
    device = connect.get("device")
    if not isinstance(device, dict):
        return None
    return _norm_str(device.get("id"))


def _denies_cross_device_management(client: Any, target_device_id: str) -> bool:
    caller_device_id = _caller_device_id(client)
    scopes = _caller_scopes(client)
    is_admin = "operator.admin" in scopes
    return bool(caller_device_id and caller_device_id != target_device_id.strip() and not is_admin)


def _summarize_tokens(tokens: Any) -> dict[str, Any]:
    if not isinstance(tokens, dict):
        return {}
    out: dict[str, Any] = {}
    for role, entry in tokens.items():
        if not isinstance(entry, dict):
            continue
        out[str(role)] = {
            "role": str(entry.get("role") or role),
            "scopes": list(entry.get("scopes") or []),
            "createdAtMs": entry.get("createdAtMs"),
            "rotatedAtMs": entry.get("rotatedAtMs"),
            "revokedAtMs": entry.get("revokedAtMs"),
        }
    return out


def _redact_paired_device(device: Any) -> dict[str, Any]:
    if not isinstance(device, dict):
        return {}
    out = dict(device)
    out["tokens"] = _summarize_tokens(device.get("tokens"))
    if "approvedScopes" in out:
        del out["approvedScopes"]
    return out


def _get_device_service(context: Any) -> Any | None:
    if isinstance(context, dict):
        return context.get("device_pairing")
    return None


def _device_pair_list_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if params is not None and not isinstance(params, dict):
        _bad(respond, "invalid device.pair.list params")
        return
    svc = _get_device_service(context)
    if svc is not None and callable(getattr(svc, "list", None)):
        listed = svc.list()
        if isinstance(listed, dict):
            paired = listed.get("paired")
            pending = listed.get("pending")
            _ok(
                respond,
                {
                    "pending": pending if isinstance(pending, list) else [],
                    "paired": [_redact_paired_device(x) for x in (paired if isinstance(paired, list) else [])],
                },
            )
            return
    _ok(respond, {"pending": [], "paired": []})


def _device_pair_approve_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    client = opts.get("client")
    if not isinstance(params, dict):
        _bad(respond, "invalid device.pair.approve params")
        return
    request_id = _norm_str(params.get("requestId"))
    if not request_id:
        _bad(respond, "invalid device.pair.approve params")
        return
    svc = _get_device_service(context)
    caller_scopes = _caller_scopes(client)
    if svc is not None and callable(getattr(svc, "approve", None)):
        approved = svc.approve(request_id, {"callerScopes": caller_scopes})
        if not approved:
            _bad(respond, "unknown requestId")
            return
        if isinstance(approved, dict) and approved.get("status") == "forbidden":
            _bad(respond, str(approved.get("message") or "device pairing forbidden"))
            return
        device = approved.get("device") if isinstance(approved, dict) else {}
        _ok(respond, {"requestId": request_id, "device": _redact_paired_device(device)})
        return
    _ok(respond, {"requestId": request_id, "device": {"deviceId": "unknown"}})


def _device_pair_reject_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid device.pair.reject params")
        return
    request_id = _norm_str(params.get("requestId"))
    if not request_id:
        _bad(respond, "invalid device.pair.reject params")
        return
    svc = _get_device_service(context)
    if svc is not None and callable(getattr(svc, "reject", None)):
        rejected = svc.reject(request_id)
        if not rejected:
            _bad(respond, "unknown requestId")
            return
        _ok(respond, rejected)
        return
    _ok(respond, {"requestId": request_id, "deviceId": "unknown", "decision": "rejected"})


def _device_pair_remove_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    client = opts.get("client")
    if not isinstance(params, dict):
        _bad(respond, "invalid device.pair.remove params")
        return
    device_id = _norm_str(params.get("deviceId"))
    if not device_id:
        _bad(respond, "invalid device.pair.remove params")
        return
    if _denies_cross_device_management(client, device_id):
        _bad(respond, "device pairing removal denied")
        return
    svc = _get_device_service(context)
    if svc is not None and callable(getattr(svc, "remove", None)):
        removed = svc.remove(device_id)
        if not removed:
            _bad(respond, "unknown deviceId")
            return
        _ok(respond, removed)
        return
    _ok(respond, {"deviceId": device_id, "removed": True})


def _device_token_rotate_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    client = opts.get("client")
    if not isinstance(params, dict):
        _bad(respond, "invalid device.token.rotate params")
        return
    device_id = _norm_str(params.get("deviceId"))
    role = _norm_str(params.get("role"))
    scopes = params.get("scopes")
    if not device_id or not role:
        _bad(respond, "invalid device.token.rotate params")
        return
    if _denies_cross_device_management(client, device_id):
        _bad(respond, DEVICE_TOKEN_ROTATION_DENIED_MESSAGE)
        return
    svc = _get_device_service(context)
    if svc is not None and callable(getattr(svc, "rotate_token", None)):
        rotated = svc.rotate_token({"deviceId": device_id, "role": role, "scopes": scopes})
        if not isinstance(rotated, dict) or not rotated.get("ok"):
            _bad(respond, DEVICE_TOKEN_ROTATION_DENIED_MESSAGE)
            return
        entry = rotated.get("entry") if isinstance(rotated.get("entry"), dict) else {}
        _ok(
            respond,
            {
                "deviceId": device_id,
                "role": str(entry.get("role") or role),
                "token": entry.get("token"),
                "scopes": entry.get("scopes") if isinstance(entry.get("scopes"), list) else [],
                "rotatedAtMs": entry.get("rotatedAtMs") or entry.get("createdAtMs"),
            },
        )
        return
    _ok(
        respond,
        {
            "deviceId": device_id,
            "role": role,
            "token": "token",
            "scopes": scopes if isinstance(scopes, list) else [],
            "rotatedAtMs": None,
        },
    )


def _device_token_revoke_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    client = opts.get("client")
    if not isinstance(params, dict):
        _bad(respond, "invalid device.token.revoke params")
        return
    device_id = _norm_str(params.get("deviceId"))
    role = _norm_str(params.get("role"))
    if not device_id or not role:
        _bad(respond, "invalid device.token.revoke params")
        return
    if _denies_cross_device_management(client, device_id):
        _bad(respond, "device token revocation denied")
        return
    svc = _get_device_service(context)
    if svc is not None and callable(getattr(svc, "revoke_token", None)):
        entry = svc.revoke_token({"deviceId": device_id, "role": role})
        if not isinstance(entry, dict):
            _bad(respond, "unknown deviceId/role")
            return
        _ok(
            respond,
            {
                "deviceId": device_id,
                "role": str(entry.get("role") or role),
                "revokedAtMs": entry.get("revokedAtMs"),
            },
        )
        return
    _ok(respond, {"deviceId": device_id, "role": role, "revokedAtMs": None})


device_handlers: GatewayRequestHandlers = {
    "device.pair.list": _device_pair_list_handler,
    "device.pair.approve": _device_pair_approve_handler,
    "device.pair.reject": _device_pair_reject_handler,
    "device.pair.remove": _device_pair_remove_handler,
    "device.token.rotate": _device_token_rotate_handler,
    "device.token.revoke": _device_token_revoke_handler,
}

