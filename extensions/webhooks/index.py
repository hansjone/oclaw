from __future__ import annotations

from .config import resolve_webhooks_plugin_config
from .http import TaskFlowWebhookTarget, create_taskflow_webhook_request_handler


def register_webhook_routes(api) -> None:
    routes = resolve_webhooks_plugin_config(plugin_config=getattr(api, "plugin_config", {}) or {})
    if not routes:
        return
    targets_by_path: dict[str, list[TaskFlowWebhookTarget]] = {}
    handler = create_taskflow_webhook_request_handler(cfg=getattr(api, "config", {}) or {}, targets_by_path=targets_by_path)
    for route in routes:
        task_flow = api.runtime.task_flow.bind_session(session_key=route.session_key)
        target = TaskFlowWebhookTarget(
            route_id=route.route_id,
            path=route.path,
            secret_input=route.secret,
            secret_config_path=f"plugins.entries.webhooks.routes.{route.route_id}.secret",
            default_controller_id=route.controller_id,
            task_flow=task_flow,
        )
        targets_by_path.setdefault(target.path, []).append(target)
        api.register_http_route(path=target.path, auth="plugin", match="exact", replace_existing=True, handler=handler)
        api.logger.info(f"[webhooks] registered route {route.route_id} on {route.path} for session {route.session_key}")

