"""WS runtime implementation under oclaw namespace."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict, deque
from typing import Any
import threading

from fastapi import WebSocket

from interfaces.gateway.dispatcher import build_gateway_method_handlers, method_names
from interfaces.ws.auth_and_hello import build_hello_ok_payload, resolve_ws_auth as resolve_ws_auth_payload
from interfaces.ws.common import (
    MAX_BUFFERED_BYTES,
    MAX_PAYLOAD_BYTES,
    PREAUTH_HANDSHAKE_TIMEOUT_MS,
    PROTOCOL_VERSION,
    TICK_INTERVAL_MS,
    WS_EVENT_REPLAY_MAX,
    WS_RATE_LIMIT_CONN_PER_WINDOW,
    WS_RATE_LIMIT_IP_PER_WINDOW,
    WS_RATE_LIMIT_USER_PER_WINDOW,
    WS_RATE_LIMIT_WINDOW_MS,
    WS_SEND_QUEUE_MAX_BYTES,
    WS_SEND_QUEUE_MAX_MESSAGES,
    error_shape as _error_shape,
    normalize_ws_attachments as _normalize_ws_attachments,
    now_ms as _now_ms,
    origin_is_allowed,
)
from interfaces.ws.events import (
    emit_agent_event as emit_agent_event_impl,
    emit_chat_event as emit_chat_event_impl,
    send_event as send_event_impl,
    send_res as send_res_impl,
)
from interfaces.ws.runtime_dispatch import dispatch_connected as dispatch_connected_impl
from interfaces.ws.runtime_helpers import handle_connect as handle_connect_impl, recv_frame as recv_frame_impl
from interfaces.ws.runtime_loop import close_ws as close_ws_impl, run_connection_loop
from interfaces.ws.server_methods_bridge import build_gateway_context, dispatch_via_server_methods
from interfaces.ws.turn_runner import run_agent_turn_via_bridge
from interfaces.ws.ws_schema import format_validation_errors, get_ws_schemas, validate_or_errors
from runtime.relay_pointer import validate_relay_share_envelope

_LOG = logging.getLogger(__name__)


class OclawWsGatewayConnection:
    _rate_lock = threading.Lock()
    _rate_by_ip: dict[str, deque[int]] = defaultdict(deque)
    _rate_by_user: dict[str, deque[int]] = defaultdict(deque)
    _stats: dict[str, int] = defaultdict(int)
    _event_buffer_by_user: dict[str, deque[dict[str, Any]]] = defaultdict(
        lambda: deque(maxlen=max(1, int(WS_EVENT_REPLAY_MAX)))
    )

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
        self._send_queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue(maxsize=WS_SEND_QUEUE_MAX_MESSAGES)
        self._send_pending_bytes = 0
        self._send_pending_lock = asyncio.Lock()
        self._sender_task: asyncio.Task[None] | None = None
        self._event_buffer: deque[dict[str, Any]] = deque(maxlen=max(1, int(WS_EVENT_REPLAY_MAX)))
        self._rate_local: deque[int] = deque()
        self._gateway_handlers = build_gateway_method_handlers()
        self._now_ms = _now_ms
        self._error_shape = _error_shape

    async def run(self) -> None:
        self._inc_stat("ws_connections_opened")
        self._sender_task = asyncio.create_task(self._sender_loop())
        try:
            await run_connection_loop(self)
        finally:
            await self._drain_sender()
            self._inc_stat("ws_connections_closed")
            _LOG.info(
                "ws connection closed conn_id=%s total_opened=%s total_closed=%s",
                self.conn_id,
                self._stats.get("ws_connections_opened", 0),
                self._stats.get("ws_connections_closed", 0),
            )

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
        limited, bucket = self._rate_limited()
        if limited:
            self._inc_stat("ws_rate_limited")
            await self.send_res(
                req_id,
                ok=False,
                error=_error_shape("RATE_LIMITED", "too many requests", details={"bucket": bucket}),
            )
            return
        await dispatch_connected_impl(self, req_id=req_id, method=method, params=params)

    @classmethod
    def _inc_stat(cls, key: str, delta: int = 1) -> None:
        with cls._rate_lock:
            cls._stats[str(key)] = int(cls._stats.get(str(key), 0)) + int(delta)

    def mark_handshake(self, *, ok: bool) -> None:
        self._inc_stat("ws_handshake_ok" if ok else "ws_handshake_failed")
        _LOG.info(
            "ws handshake conn_id=%s ok=%s user_id=%s",
            self.conn_id,
            int(bool(ok)),
            str((self.auth_ctx or {}).get("user_id") or ""),
        )

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

    def validate_origin(self) -> bool:
        headers = getattr(self.ws, "headers", None)
        origin = str(headers.get("origin") or "").strip() if headers is not None else ""
        host = str(headers.get("host") or "").strip() if headers is not None else ""
        allowed = origin_is_allowed(origin, host)
        if not allowed:
            _LOG.warning("ws origin blocked conn_id=%s origin=%s host=%s", self.conn_id, origin, host)
        return allowed

    def _prune_window(self, dq: deque[int], now: int) -> None:
        cutoff = now - int(WS_RATE_LIMIT_WINDOW_MS)
        while dq and dq[0] < cutoff:
            dq.popleft()

    def _rate_limited(self) -> tuple[bool, str]:
        now = _now_ms()
        self._prune_window(self._rate_local, now)
        if len(self._rate_local) >= int(WS_RATE_LIMIT_CONN_PER_WINDOW):
            return True, "connection"
        self._rate_local.append(now)

        headers = getattr(self.ws, "headers", None)
        ip = str(headers.get("x-forwarded-for") or headers.get("x-real-ip") or "").split(",")[0].strip() if headers is not None else ""
        user_id = str((self.auth_ctx or {}).get("user_id") or "").strip()
        with self._rate_lock:
            if ip:
                ip_bucket = self._rate_by_ip[ip]
                self._prune_window(ip_bucket, now)
                if len(ip_bucket) >= int(WS_RATE_LIMIT_IP_PER_WINDOW):
                    return True, "ip"
                ip_bucket.append(now)
            if user_id:
                user_bucket = self._rate_by_user[user_id]
                self._prune_window(user_bucket, now)
                if len(user_bucket) >= int(WS_RATE_LIMIT_USER_PER_WINDOW):
                    return True, "user"
                user_bucket.append(now)
        return False, ""

    async def _queue_send_text(self, text: str) -> bool:
        payload = str(text or "")
        payload_size = len(payload.encode("utf-8", errors="ignore"))
        async with self._send_pending_lock:
            if self._send_pending_bytes + payload_size > int(WS_SEND_QUEUE_MAX_BYTES):
                _LOG.warning("ws send queue bytes exceeded conn_id=%s", self.conn_id)
                return False
            self._send_pending_bytes += payload_size
        try:
            self._send_queue.put_nowait((payload, payload_size))
            return True
        except asyncio.QueueFull:
            async with self._send_pending_lock:
                self._send_pending_bytes = max(0, self._send_pending_bytes - payload_size)
            _LOG.warning("ws send queue full conn_id=%s", self.conn_id)
            return False

    async def _sender_loop(self) -> None:
        while True:
            item = await self._send_queue.get()
            if item[0] == "__STOP__":
                self._send_queue.task_done()
                return
            payload, payload_size = item
            try:
                await self.ws.send_text(payload)
            except Exception:
                return
            finally:
                async with self._send_pending_lock:
                    self._send_pending_bytes = max(0, self._send_pending_bytes - payload_size)
                self._send_queue.task_done()

    async def _drain_sender(self) -> None:
        if self._sender_task is None:
            return
        try:
            self._send_queue.put_nowait(("__STOP__", 0))
        except Exception:
            pass
        try:
            await self._sender_task
        except Exception:
            pass
        self._sender_task = None

    def remember_event(self, frame: dict[str, Any]) -> None:
        snap = dict(frame or {})
        self._event_buffer.append(snap)
        user_id = str((self.auth_ctx or {}).get("user_id") or "").strip()
        if not user_id:
            return
        with self._rate_lock:
            bucket = self._event_buffer_by_user.get(user_id)
            if bucket is None or bucket.maxlen != max(1, int(WS_EVENT_REPLAY_MAX)):
                bucket = deque(maxlen=max(1, int(WS_EVENT_REPLAY_MAX)))
                self._event_buffer_by_user[user_id] = bucket
            bucket.append(dict(snap))

    async def replay_events_since(self, seq: int) -> None:
        after = int(seq or 0)
        frames = list(self._event_buffer)
        user_id = str((self.auth_ctx or {}).get("user_id") or "").strip()
        if user_id:
            with self._rate_lock:
                shared = list(self._event_buffer_by_user.get(user_id) or [])
            if shared:
                frames = shared
        for frame in frames:
            fseq = int(frame.get("seq") or 0)
            if fseq <= after:
                continue
            text = frame.get("_raw")
            if not isinstance(text, str) or not text:
                continue
            await self._queue_send_text(text)

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

