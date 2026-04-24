from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from typing import Any

from .runtime_api import resolve_configured_secret_input_string


@dataclass(frozen=True)
class TaskFlowWebhookTarget:
    route_id: str
    path: str
    secret_input: str | dict[str, str]
    secret_config_path: str
    default_controller_id: str
    task_flow: Any


def _pick_optional(data: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in keys:
        if key in data and data[key] is not None:
            out[key] = data[key]
    return out


def _to_flow_view(flow: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(flow, dict):
        return None
    keep = {
        "flowId",
        "syncMode",
        "controllerId",
        "revision",
        "status",
        "notifyPolicy",
        "goal",
        "currentStep",
        "blockedTaskId",
        "blockedSummary",
        "stateJson",
        "waitJson",
        "cancelRequestedAt",
        "createdAt",
        "updatedAt",
        "endedAt",
    }
    return {k: v for k, v in flow.items() if k in keep and v is not None}


def _to_task_view(task: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(task, dict):
        return None
    keep = {
        "taskId",
        "runtime",
        "sourceId",
        "scopeKind",
        "childSessionKey",
        "parentFlowId",
        "parentTaskId",
        "agentId",
        "runId",
        "label",
        "task",
        "status",
        "deliveryStatus",
        "notifyPolicy",
        "createdAt",
        "startedAt",
        "endedAt",
        "lastEventAt",
        "cleanupAfter",
        "error",
        "progressSummary",
        "terminalSummary",
        "terminalOutcome",
    }
    return {k: v for k, v in task.items() if k in keep and v is not None}


def _timing_safe_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _extract_secret(headers: dict[str, str]) -> str:
    auth = str(headers.get("authorization") or "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return str(headers.get("x-openclaw-webhook-secret") or "").strip()


def _map_mutation_status(result: dict[str, Any]) -> tuple[int, str | None, str | None]:
    if bool(result.get("applied")):
        return (200, None, None)
    code = str(result.get("code") or "").strip()
    if code == "not_found":
        return (404, "not_found", "TaskFlow not found.")
    if code == "not_managed":
        return (409, "not_managed", "TaskFlow is not managed by this webhook surface.")
    if code == "revision_conflict":
        return (409, "revision_conflict", "TaskFlow changed since the caller's expected revision.")
    return (409, "mutation_rejected", "TaskFlow mutation was rejected.")


def _map_run_task_status(result: dict[str, Any]) -> tuple[int, str | None, str | None]:
    if bool(result.get("created")):
        return (200, None, None)
    if not bool(result.get("found", True)):
        return (404, "not_found", "TaskFlow not found.")
    reason = str(result.get("reason") or "").strip()
    if reason == "Flow cancellation has already been requested.":
        return (409, "cancel_requested", reason)
    if reason == "Flow does not accept managed child tasks.":
        return (409, "not_managed", reason)
    if reason.startswith("Flow is already "):
        return (409, "terminal", reason)
    return (409, "task_not_created", reason or "TaskFlow task was not created.")


def _map_cancel_status(result: dict[str, Any]) -> tuple[int, str | None, str | None]:
    if bool(result.get("cancelled")):
        return (200, None, None)
    if not bool(result.get("found", True)):
        return (404, "not_found", "TaskFlow not found.")
    reason = str(result.get("reason") or "").strip()
    if reason == "One or more child tasks are still active.":
        return (202, "cancel_pending", reason)
    if reason == "Flow changed while cancellation was in progress.":
        return (409, "revision_conflict", reason)
    if reason.startswith("Flow is already "):
        return (409, "terminal", reason)
    return (409, "cancel_rejected", reason or "TaskFlow cancellation was rejected.")


def _describe_webhook_outcome(action_name: str, result: dict[str, Any]) -> tuple[int, str | None, str | None]:
    if action_name in {"set_waiting", "resume_flow", "finish_flow", "fail_flow", "request_cancel"}:
        return _map_mutation_status(result)
    if action_name == "cancel_flow":
        return _map_cancel_status(result)
    if action_name == "run_task":
        return _map_run_task_status(result)
    return (200, None, None)


def _map_flow_mutation_result(result: dict[str, Any]) -> dict[str, Any]:
    if bool(result.get("applied")):
        flow = _to_flow_view(result.get("flow") if isinstance(result.get("flow"), dict) else None)
        return {"applied": True, "flow": flow}
    current = result.get("current")
    out = {
        "applied": False,
        "code": str(result.get("code") or ""),
    }
    if isinstance(current, dict):
        out["current"] = _to_flow_view(current)
    return out


def execute_webhook_action(*, action: dict[str, Any], target: TaskFlowWebhookTarget, cfg: dict[str, Any]) -> dict[str, Any]:
    name = str(action.get("action") or "").strip()
    tf = target.task_flow
    if name == "create_flow":
        flow = tf.create_managed(
            controller_id=action.get("controllerId") or target.default_controller_id,
            goal=action["goal"],
            status=action.get("status"),
            notify_policy=action.get("notifyPolicy"),
            current_step=action.get("currentStep"),
            state_json=action.get("stateJson"),
            wait_json=action.get("waitJson"),
        )
        return {"flow": _to_flow_view(flow)}
    if name == "get_flow":
        flow = tf.get(action["flowId"])
        return {"flow": _to_flow_view(flow)}
    if name == "list_flows":
        flows = tf.list()
        return {"flows": [_to_flow_view(x) for x in flows]}
    if name == "find_latest_flow":
        flow = tf.find_latest()
        return {"flow": _to_flow_view(flow)}
    if name == "resolve_flow":
        flow = tf.resolve(action["token"])
        return {"flow": _to_flow_view(flow)}
    if name == "get_task_summary":
        return {"summary": tf.get_task_summary(action["flowId"])}
    if name == "set_waiting":
        raw = tf.set_waiting(
            flow_id=action["flowId"],
            expected_revision=action["expectedRevision"],
            current_step=action.get("currentStep"),
            state_json=action.get("stateJson"),
            wait_json=action.get("waitJson"),
            blocked_task_id=action.get("blockedTaskId"),
            blocked_summary=action.get("blockedSummary"),
        )
        return _map_flow_mutation_result(raw if isinstance(raw, dict) else {})
    if name == "resume_flow":
        raw = tf.resume(
            flow_id=action["flowId"],
            expected_revision=action["expectedRevision"],
            status=action.get("status"),
            current_step=action.get("currentStep"),
            state_json=action.get("stateJson"),
        )
        return _map_flow_mutation_result(raw if isinstance(raw, dict) else {})
    if name == "finish_flow":
        raw = tf.finish(
            flow_id=action["flowId"],
            expected_revision=action["expectedRevision"],
            state_json=action.get("stateJson"),
        )
        return _map_flow_mutation_result(raw if isinstance(raw, dict) else {})
    if name == "fail_flow":
        raw = tf.fail(
            flow_id=action["flowId"],
            expected_revision=action["expectedRevision"],
            state_json=action.get("stateJson"),
            blocked_task_id=action.get("blockedTaskId"),
            blocked_summary=action.get("blockedSummary"),
        )
        return _map_flow_mutation_result(raw if isinstance(raw, dict) else {})
    if name == "request_cancel":
        raw = tf.request_cancel(
            flow_id=action["flowId"],
            expected_revision=action["expectedRevision"],
        )
        return _map_flow_mutation_result(raw if isinstance(raw, dict) else {})
    if name == "cancel_flow":
        raw = tf.cancel(flow_id=action["flowId"], cfg=cfg)
        if not isinstance(raw, dict):
            return {"found": False, "cancelled": False, "reason": "invalid cancel result"}
        out = {
            "found": bool(raw.get("found")),
            "cancelled": bool(raw.get("cancelled")),
        }
        if raw.get("reason") is not None:
            out["reason"] = str(raw.get("reason"))
        flow = _to_flow_view(raw.get("flow") if isinstance(raw.get("flow"), dict) else None)
        if flow is not None:
            out["flow"] = flow
        tasks = raw.get("tasks")
        if isinstance(tasks, list):
            out["tasks"] = [_to_task_view(t if isinstance(t, dict) else None) for t in tasks]
        return out
    if name == "run_task":
        raw = tf.run_task(
            flow_id=action["flowId"],
            runtime=action["runtime"],
            source_id=action.get("sourceId"),
            child_session_key=action.get("childSessionKey"),
            parent_task_id=action.get("parentTaskId"),
            agent_id=action.get("agentId"),
            run_id=action.get("runId"),
            label=action.get("label"),
            task=action["task"],
            prefer_metadata=action.get("preferMetadata"),
            notify_policy=action.get("notifyPolicy"),
            status=action.get("status"),
            started_at=action.get("startedAt"),
            last_event_at=action.get("lastEventAt"),
            progress_summary=action.get("progressSummary"),
        )
        if not isinstance(raw, dict):
            return {"found": False, "created": False, "reason": "invalid run_task result"}
        if bool(raw.get("created")):
            return {
                "created": True,
                "flow": _to_flow_view(raw.get("flow") if isinstance(raw.get("flow"), dict) else None),
                "task": _to_task_view(raw.get("task") if isinstance(raw.get("task"), dict) else None),
            }
        out = {
            "found": bool(raw.get("found")),
            "created": False,
            "reason": str(raw.get("reason") or ""),
        }
        flow = _to_flow_view(raw.get("flow") if isinstance(raw.get("flow"), dict) else None)
        if flow is not None:
            out["flow"] = flow
        return out
    raise ValueError(f"unsupported webhook action: {name}")


def create_taskflow_webhook_request_handler(*, cfg: dict[str, Any], targets_by_path: dict[str, list[TaskFlowWebhookTarget]]):
    def handle(request: dict[str, Any]) -> dict[str, Any]:
        path = str(request.get("path") or "/")
        targets = list(targets_by_path.get(path) or [])
        if not targets:
            return {"ok": False, "code": "not_found", "error": "route not found"}
        headers = request.get("headers")
        headers = headers if isinstance(headers, dict) else {}
        presented = _extract_secret({str(k).lower(): str(v) for k, v in headers.items()})
        if not presented:
            return {"ok": False, "code": "unauthorized", "error": "missing webhook secret"}
        matched: TaskFlowWebhookTarget | None = None
        for target in targets:
            resolved = resolve_configured_secret_input_string(value=target.secret_input)
            if resolved and _timing_safe_equals(resolved, presented):
                matched = target
                break
        if matched is None:
            return {"ok": False, "code": "unauthorized", "error": "invalid webhook secret"}
        body = request.get("json")
        if isinstance(body, str):
            body = json.loads(body)
        if not isinstance(body, dict):
            return {"ok": False, "code": "invalid_request", "error": "request body must be json object"}
        try:
            action_name = str(body.get("action") or "").strip()
            result = execute_webhook_action(action=body, target=matched, cfg=cfg)
        except Exception as exc:
            return {
                "ok": False,
                "routeId": matched.route_id,
                "code": "request_rejected",
                "error": str(exc),
            }
        status_code, code, error = _describe_webhook_outcome(action_name, result if isinstance(result, dict) else {})
        if status_code < 400:
            out = {"ok": True, "routeId": matched.route_id, "statusCode": status_code, "result": result}
            if code:
                out["code"] = code
            return out
        out = {
            "ok": False,
            "routeId": matched.route_id,
            "statusCode": status_code,
            "code": code or "request_rejected",
            "error": error or "request rejected",
            "result": result,
        }
        return out

    return handle

