"""WS runtime implementation under oclaw namespace."""

from __future__ import annotations

import uuid
from typing import Any
import threading

from fastapi import WebSocket

from oclaw.interfaces.gateway.dispatcher import build_gateway_method_handlers, method_names
from oclaw.interfaces.ws.auth_and_hello import build_hello_ok_payload, resolve_ws_auth as resolve_ws_auth_payload
from oclaw.interfaces.ws.common import (
    MAX_BUFFERED_BYTES,
    MAX_PAYLOAD_BYTES,
    PREAUTH_HANDSHAKE_TIMEOUT_MS,
    PROTOCOL_VERSION,
    TICK_INTERVAL_MS,
    error_shape as _error_shape,
    normalize_ws_attachments as _normalize_ws_attachments,
    now_ms as _now_ms,
)
from oclaw.interfaces.ws.events import (
    emit_agent_event as emit_agent_event_impl,
    emit_chat_event as emit_chat_event_impl,
    send_event as send_event_impl,
    send_res as send_res_impl,
)
from oclaw.interfaces.ws.runtime_dispatch import dispatch_connected as dispatch_connected_impl
from oclaw.interfaces.ws.runtime_helpers import handle_connect as handle_connect_impl, recv_frame as recv_frame_impl
from oclaw.interfaces.ws.runtime_loop import close_ws as close_ws_impl, run_connection_loop
from oclaw.interfaces.ws.server_methods_bridge import build_gateway_context, dispatch_via_server_methods
from oclaw.interfaces.ws.turn_runner import run_agent_turn_via_bridge
from oclaw.interfaces.ws.ws_schema import format_validation_errors, get_ws_schemas, validate_or_errors
from oclaw.openclaw_runtime.relay_pointer import validate_relay_share_envelope


class OclawWsGatewayConnection:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.schemas = get_ws_schemas()
        self.connected = False
        self.conn_id = uuid.uuid4().hex[:12]
        self.seq = 0
        self.started_at_ms = _now_ms()
        self.client_meta: dict[str, Any] | None = None
        self._is_webchat_client = False
        self.role = "operator"
        self.scopes: list[str] = []
        self.auth_ctx: dict[str, Any] | None = None
        self.connect_nonce = uuid.uuid4().hex
        self.handshake_failed = False
        self._subscribed_sessions_changed = False
        self._subscribed_message_keys: set[str] = set()
        self._abort_lock = threading.Lock()
        self._aborted_run_ids: set[str] = set()
        self._active_run_session: dict[str, str] = {}
        self._gateway_handlers = build_gateway_method_handlers()
        self._now_ms = _now_ms
        self._error_shape = _error_shape

    async def run(self) -> None:
        await run_connection_loop(self)

    async def _recv_frame(self, *, preauth: bool = False) -> dict[str, Any] | None:
        return await recv_frame_impl(
            conn=self,
            preauth=preauth,
            handshake_timeout_ms=PREAUTH_HANDSHAKE_TIMEOUT_MS,
            validate_or_errors=validate_or_errors,
            format_validation_errors=format_validation_errors,
            error_shape=_error_shape,
        )

    async def _handle_connect(self, req_id: str, method: str, params: Any) -> None:
        await handle_connect_impl(
            conn=self,
            req_id=req_id,
            method=method,
            params=params,
            protocol_version=PROTOCOL_VERSION,
            validate_or_errors=validate_or_errors,
            format_validation_errors=format_validation_errors,
            error_shape=_error_shape,
        )

    async def _close_ws(self, code: int = 1000, reason: str = "done") -> None:
        await close_ws_impl(self, code=code, reason=reason)

    async def _dispatch_connected(self, req_id: str, method: str, params: Any) -> None:
        await dispatch_connected_impl(self, req_id=req_id, method=method, params=params)

    async def _dispatch_via_server_methods(self, *, req_id: str, method: str, params: Any) -> bool:
        return await dispatch_via_server_methods(
            req_id=req_id,
            method=method,
            params=params,
            conn_id=self.conn_id,
            is_webchat_client=bool(self._is_webchat_client),
            handlers=self._gateway_handlers,
            context=self._build_gateway_context(),
            send_res=self.send_res,
            error_shape=_error_shape,
        )

    def _build_gateway_context(self) -> dict[str, Any]:
        return build_gateway_context(
            conn_id=self.conn_id,
            subscribed_sessions_changed=bool(self._subscribed_sessions_changed),
            subscribed_message_keys=set(self._subscribed_message_keys),
            abort_lock=self._abort_lock,
            active_run_session=self._active_run_session,
            aborted_run_ids=self._aborted_run_ids,
            run_agent_turn=self.run_agent_turn,
            normalize_ws_attachments=_normalize_ws_attachments,
            validate_relay_share_envelope=validate_relay_share_envelope,
            now_ms=_now_ms,
        )

    def build_hello_ok(self, _connect_params: dict[str, Any] | None) -> dict[str, Any]:
        methods = ["connect", *method_names()]
        return build_hello_ok_payload(
            conn_id=self.conn_id,
            started_at_ms=int(self.started_at_ms or _now_ms()),
            role=str(self.role or "operator"),
            scopes=list(self.scopes or []),
            protocol_version=PROTOCOL_VERSION,
            methods=methods,
            max_payload_bytes=MAX_PAYLOAD_BYTES,
            max_buffered_bytes=MAX_BUFFERED_BYTES,
            tick_interval_ms=TICK_INTERVAL_MS,
            now_ms=_now_ms(),
        )

    async def send_res(self, req_id: str, *, ok: bool, payload: Any | None = None, error: Any | None = None) -> None:
        await send_res_impl(self, req_id, ok=ok, payload=payload, error=error)

    async def send_event(self, event: str, payload: Any | None = None) -> None:
        await send_event_impl(self, event, payload)

    async def emit_agent_event(self, *, run_id: str, stream: str, data: dict[str, Any]) -> None:
        await emit_agent_event_impl(self, run_id=run_id, stream=stream, data=data, now_ms=_now_ms())

    async def emit_chat_event(
        self,
        *,
        run_id: str,
        state: str,
        delta: str = "",
        reply: str = "",
        error: str = "",
        message: dict[str, Any] | None = None,
        session_key: str | None = None,
        seq: int | None = None,
    ) -> None:
        await emit_chat_event_impl(
            self,
            run_id=run_id,
            state=state,
            delta=delta,
            reply=reply,
            error=error,
            message=message,
            session_key=session_key,
            seq=seq,
        )

    def resolve_ws_auth(self, connect_params: dict[str, Any] | None) -> dict[str, Any]:
        return resolve_ws_auth_payload(connect_params)

    async def run_agent_turn(self, req_id: str, p: dict[str, Any], *, session_id: str, send_response: bool = True) -> None:
        await run_agent_turn_via_bridge(
            conn=self,
            req_id=req_id,
            p=p,
            session_id=session_id,
            send_response=send_response,
            normalize_ws_attachments=_normalize_ws_attachments,
            validate_relay_share_envelope=validate_relay_share_envelope,
            now_ms=_now_ms,
            error_shape=_error_shape,
        )


async def ws_gateway_loop(ws: WebSocket) -> None:
    await OclawWsGatewayConnection(ws).run()


__all__ = ["OclawWsGatewayConnection", "ws_gateway_loop"]

