from __future__ import annotations

from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _ok(respond, payload: Any) -> None:
    if callable(respond):
        respond(True, payload, None, None)


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _normalize_optional_str(v: Any) -> str | None:
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return None


def _get_cron(context: Any) -> Any | None:
    if isinstance(context, dict):
        return context.get("cron")
    return None


def _wake_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid wake params")
        return
    mode = params.get("mode")
    text = _normalize_optional_str(params.get("text"))
    if mode not in {"now", "next-heartbeat"} or not text:
        _bad(respond, "invalid wake params")
        return
    cron = _get_cron(context)
    if cron is not None and callable(getattr(cron, "wake", None)):
        _ok(respond, cron.wake({"mode": mode, "text": text}))
        return
    _ok(respond, {"ok": True, "mode": mode, "text": text})


def _cron_list_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid cron.list params")
        return
    cron = _get_cron(context)
    if cron is None or not callable(getattr(cron, "listPage", None)):
        _ok(respond, {"items": [], "total": 0})
        return
    _ok(
        respond,
        cron.listPage(
            {
                "includeDisabled": params.get("includeDisabled"),
                "limit": params.get("limit"),
                "offset": params.get("offset"),
                "query": params.get("query"),
                "enabled": params.get("enabled"),
                "sortBy": params.get("sortBy"),
                "sortDir": params.get("sortDir"),
            }
        ),
    )


def _cron_status_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    cron = _get_cron(context)
    if cron is not None and callable(getattr(cron, "status", None)):
        _ok(respond, cron.status())
        return
    _ok(respond, {"running": False})


def _cron_add_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid cron.add params")
        return
    schedule = _normalize_optional_str(params.get("schedule"))
    name = _normalize_optional_str(params.get("name"))
    if not schedule or not name:
        _bad(respond, "invalid cron.add params")
        return
    cron = _get_cron(context)
    if cron is not None and callable(getattr(cron, "add", None)):
        _ok(respond, cron.add(dict(params)))
        return
    _ok(respond, {"id": "cron_1", **params})


def _cron_update_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid cron.update params")
        return
    job_id = _normalize_optional_str(params.get("id")) or _normalize_optional_str(params.get("jobId"))
    patch = params.get("patch")
    if not job_id:
        _bad(respond, "invalid cron.update params: missing id")
        return
    if not isinstance(patch, dict):
        _bad(respond, "invalid cron.update params")
        return
    cron = _get_cron(context)
    if cron is not None and callable(getattr(cron, "update", None)):
        _ok(respond, cron.update(job_id, patch))
        return
    _ok(respond, {"id": job_id, **patch})


def _cron_remove_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid cron.remove params")
        return
    job_id = _normalize_optional_str(params.get("id")) or _normalize_optional_str(params.get("jobId"))
    if not job_id:
        _bad(respond, "invalid cron.remove params: missing id")
        return
    cron = _get_cron(context)
    if cron is not None and callable(getattr(cron, "remove", None)):
        _ok(respond, cron.remove(job_id))
        return
    _ok(respond, {"removed": True, "id": job_id})


def _cron_run_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid cron.run params")
        return
    job_id = _normalize_optional_str(params.get("id")) or _normalize_optional_str(params.get("jobId"))
    mode = _normalize_optional_str(params.get("mode")) or "force"
    if not job_id:
        _bad(respond, "invalid cron.run params: missing id")
        return
    cron = _get_cron(context)
    if cron is not None and callable(getattr(cron, "enqueueRun", None)):
        try:
            _ok(respond, cron.enqueueRun(job_id, mode))
            return
        except Exception:
            _ok(respond, {"ok": True, "ran": False, "reason": "invalid-spec"})
            return
    _ok(respond, {"ok": True, "ran": True, "jobId": job_id, "mode": mode})


def _cron_runs_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid cron.runs params")
        return
    scope = _normalize_optional_str(params.get("scope"))
    job_id = _normalize_optional_str(params.get("id")) or _normalize_optional_str(params.get("jobId"))
    resolved_scope = scope or ("job" if job_id else "all")
    if resolved_scope == "job" and not job_id:
        _bad(respond, "invalid cron.runs params: missing id")
        return
    cron = _get_cron(context)
    if cron is not None and callable(getattr(cron, "listRuns", None)):
        _ok(
            respond,
            cron.listRuns(
                {
                    "scope": resolved_scope,
                    "jobId": job_id,
                    "limit": params.get("limit"),
                    "offset": params.get("offset"),
                    "statuses": params.get("statuses"),
                    "status": params.get("status"),
                    "deliveryStatuses": params.get("deliveryStatuses"),
                    "deliveryStatus": params.get("deliveryStatus"),
                    "query": params.get("query"),
                    "sortDir": params.get("sortDir"),
                }
            ),
        )
        return
    _ok(respond, {"items": [], "total": 0, "scope": resolved_scope, "jobId": job_id})


cron_handlers: GatewayRequestHandlers = {
    "wake": _wake_handler,
    "cron.list": _cron_list_handler,
    "cron.status": _cron_status_handler,
    "cron.add": _cron_add_handler,
    "cron.update": _cron_update_handler,
    "cron.remove": _cron_remove_handler,
    "cron.run": _cron_run_handler,
    "cron.runs": _cron_runs_handler,
}

