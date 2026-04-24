from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict


class ErrorShape(TypedDict, total=False):
    code: str
    message: str
    data: dict[str, Any]


class GatewayClient(TypedDict, total=False):
    connect: dict[str, Any]
    conn_id: str
    client_ip: str
    canvas_host_url: str
    canvas_capability: str
    canvas_capability_expires_at_ms: int
    internal: dict[str, Any]


RespondFn = Callable[[bool, Any | None, ErrorShape | None, dict[str, Any] | None], None]


class GatewayRequestContext(TypedDict, total=False):
    deps: Any
    cron: Any
    cron_store_path: str
    get_health_cache: Callable[[], Any | None]
    refresh_health_snapshot: Callable[..., Any]
    log_health: Any
    log_gateway: Any
    unavailable_gateway_methods: set[str]


class GatewayRequestHandlerOptions(TypedDict, total=False):
    req: dict[str, Any]
    params: dict[str, Any]
    client: GatewayClient | None
    is_webchat_connect: Callable[[dict[str, Any] | None], bool]
    respond: RespondFn
    context: GatewayRequestContext


GatewayRequestHandler = Callable[[GatewayRequestHandlerOptions], Any]
GatewayRequestHandlers = dict[str, GatewayRequestHandler]
