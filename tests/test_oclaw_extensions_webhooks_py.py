from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {module_name} from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _mount_webhooks_package():
    root = Path(__file__).resolve().parents[1] / "runtime" / "extensions" / "webhooks"
    pkg_root = types.ModuleType("ocx")
    pkg_root.__path__ = [str(root.parent)]
    sys.modules["ocx"] = pkg_root
    pkg = types.ModuleType("ocx.webhooks")
    pkg.__path__ = [str(root)]
    sys.modules["ocx.webhooks"] = pkg

    runtime_api = _load_module("ocx.webhooks.runtime_api", root / "runtime_api.py")
    config = _load_module("ocx.webhooks.config", root / "config.py")
    http = _load_module("ocx.webhooks.http", root / "http.py")
    return runtime_api, config, http


def test_webhooks_config_resolve_and_conflict() -> None:
    _, config, _ = _mount_webhooks_package()
    rows = config.resolve_webhooks_plugin_config(
        plugin_config={
            "routes": {
                "r1": {
                    "sessionKey": "s1",
                    "secret": "abc",
                }
            }
        }
    )
    assert len(rows) == 1
    assert rows[0].path == "/plugins/webhooks/r1"
    assert rows[0].controller_id == "webhooks/r1"

    try:
        config.resolve_webhooks_plugin_config(
            plugin_config={
                "routes": {
                    "a": {"path": "/x", "sessionKey": "s1", "secret": "k1"},
                    "b": {"path": "/x", "sessionKey": "s2", "secret": "k2"},
                }
            }
        )
    except ValueError as exc:
        assert "conflicts" in str(exc)
    else:
        raise AssertionError("expected conflict error")


class _TaskFlow:
    def create_managed(self, **kwargs):
        return {"flowId": "f1", "goal": kwargs.get("goal"), "revision": 0, "status": "queued", "createdAt": 1, "updatedAt": 1}

    def get(self, flow_id: str):
        return {"flowId": flow_id, "revision": 1, "status": "running", "createdAt": 1, "updatedAt": 2}

    def list(self):
        return [self.get("f1")]

    def request_cancel(self, **kwargs):
        if kwargs.get("flow_id") == "missing":
            return {"applied": False, "code": "not_found"}
        return {"applied": True, "flow": self.get(kwargs.get("flow_id", "f1"))}

    def resume(self, **kwargs):
        flow_id = kwargs.get("flow_id")
        if flow_id == "conflict":
            return {"applied": False, "code": "revision_conflict", "current": self.get("f1")}
        return {"applied": True, "flow": self.get(flow_id or "f1")}

    def finish(self, **kwargs):
        return {"applied": True, "flow": self.get(kwargs.get("flow_id", "f1"))}

    def fail(self, **kwargs):
        return {"applied": True, "flow": self.get(kwargs.get("flow_id", "f1"))}

    def set_waiting(self, **kwargs):
        return {"applied": True, "flow": self.get(kwargs.get("flow_id", "f1"))}

    def cancel(self, **kwargs):
        flow_id = kwargs.get("flow_id")
        if flow_id == "pending":
            return {"found": True, "cancelled": False, "reason": "One or more child tasks are still active."}
        return {"found": True, "cancelled": True, "flow": self.get(flow_id or "f1"), "tasks": []}

    def run_task(self, **kwargs):
        flow_id = kwargs.get("flow_id")
        if flow_id == "missing":
            return {"created": False, "found": False, "reason": "not found"}
        if flow_id == "terminal":
            return {"created": False, "found": True, "reason": "Flow is already completed."}
        return {
            "created": True,
            "flow": self.get(flow_id or "f1"),
            "task": {
                "taskId": "t1",
                "runtime": kwargs.get("runtime", "subagent"),
                "scopeKind": "flow",
                "task": kwargs.get("task", ""),
                "status": "queued",
                "deliveryStatus": "queued",
                "notifyPolicy": "done_only",
                "createdAt": 1,
            },
        }


def test_webhooks_handler_auth_and_actions() -> None:
    _, _, http = _mount_webhooks_package()
    target = http.TaskFlowWebhookTarget(
        route_id="r1",
        path="/hooks/a",
        secret_input="sekret",
        secret_config_path="plugins.entries.webhooks.routes.r1.secret",
        default_controller_id="webhooks/r1",
        task_flow=_TaskFlow(),
    )
    handler = http.create_taskflow_webhook_request_handler(cfg={}, targets_by_path={"/hooks/a": [target]})

    unauthorized = handler({"path": "/hooks/a", "headers": {}, "json": {"action": "list_flows"}})
    assert unauthorized["ok"] is False
    assert unauthorized["code"] == "unauthorized"

    created = handler(
        {
            "path": "/hooks/a",
            "headers": {"authorization": "Bearer sekret"},
            "json": {"action": "create_flow", "goal": "ship it"},
        }
    )
    assert created["ok"] is True
    assert created["statusCode"] == 200
    assert created["result"]["flow"]["flowId"] == "f1"

    missing = handler(
        {
            "path": "/hooks/a",
            "headers": {"x-oclaw-webhook-secret": "sekret"},
            "json": {"action": "request_cancel", "flowId": "missing", "expectedRevision": 1},
        }
    )
    assert missing["ok"] is False
    assert missing["statusCode"] == 404
    assert missing["code"] == "not_found"


def test_webhooks_handler_action_status_mappings() -> None:
    _, _, http = _mount_webhooks_package()
    target = http.TaskFlowWebhookTarget(
        route_id="r2",
        path="/hooks/b",
        secret_input="sekret2",
        secret_config_path="plugins.entries.webhooks.routes.r2.secret",
        default_controller_id="webhooks/r2",
        task_flow=_TaskFlow(),
    )
    handler = http.create_taskflow_webhook_request_handler(cfg={}, targets_by_path={"/hooks/b": [target]})

    def _call(payload: dict):
        return handler(
            {
                "path": "/hooks/b",
                "headers": {"authorization": "Bearer sekret2"},
                "json": payload,
            }
        )

    resume_conflict = _call({"action": "resume_flow", "flowId": "conflict", "expectedRevision": 1})
    assert resume_conflict["ok"] is False
    assert resume_conflict["statusCode"] == 409
    assert resume_conflict["code"] == "revision_conflict"

    cancel_pending = _call({"action": "cancel_flow", "flowId": "pending"})
    assert cancel_pending["ok"] is True
    assert cancel_pending["statusCode"] == 202
    assert cancel_pending["code"] == "cancel_pending"

    run_task_missing = _call(
        {"action": "run_task", "flowId": "missing", "runtime": "subagent", "task": "ping"}
    )
    assert run_task_missing["ok"] is False
    assert run_task_missing["statusCode"] == 404
    assert run_task_missing["code"] == "not_found"

    run_task_terminal = _call(
        {"action": "run_task", "flowId": "terminal", "runtime": "subagent", "task": "ping"}
    )
    assert run_task_terminal["ok"] is False
    assert run_task_terminal["statusCode"] == 409
    assert run_task_terminal["code"] == "terminal"

    run_task_ok = _call({"action": "run_task", "flowId": "f1", "runtime": "subagent", "task": "ping"})
    assert run_task_ok["ok"] is True
    assert run_task_ok["statusCode"] == 200
    assert run_task_ok["result"]["created"] is True

