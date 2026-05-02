import unittest
from unittest import mock

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.interfaces.ws.runtime_impl import OclawWsGatewayConnection
from oclaw.runtime.gateway import OclawGatewayResult


def _connect_params() -> dict:
    return {
        "minProtocol": 3,
        "maxProtocol": 3,
        "client": {"id": "test", "version": "0.0.0", "platform": "pytest", "mode": "operator"},
        "role": "operator",
        "scopes": ["operator.read"],
        "caps": [],
        "commands": [],
        "permissions": {},
        "auth": {"token": "test-token"},
    }


class WsGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        with OclawWsGatewayConnection._rate_lock:
            OclawWsGatewayConnection._rate_by_ip.clear()
            OclawWsGatewayConnection._rate_by_user.clear()
            OclawWsGatewayConnection._stats.clear()
            OclawWsGatewayConnection._event_buffer_by_user.clear()
        self._auth_patcher = mock.patch(
            "oclaw.interfaces.ws.runtime_impl.resolve_ws_auth_payload",
            return_value={"tenant_id": "t1", "user_id": "u1", "role": "operator"},
        )
        self._auth_patcher.start()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self._auth_patcher.stop()

    def test_ws_requires_connect_first(self) -> None:
        with self.client.websocket_connect("/ws") as ws:
            # server sends connect.challenge first
            evt = ws.receive_json()
            assert evt["type"] == "event"
            assert evt["event"] == "connect.challenge"

            ws.send_json({"type": "req", "id": "1", "method": "agent", "params": {"message": "hi", "idempotencyKey": "k"}})
            res = ws.receive_json()
            assert res["type"] == "res"
            assert res["id"] == "1"
            assert res["ok"] is False
            assert (res.get("error") or {}).get("code") == "INVALID_REQUEST"

    def test_ws_connect_returns_hello_ok(self) -> None:
        with self.client.websocket_connect("/ws") as ws:
            ws.receive_json()  # connect.challenge
            ws.send_json({"type": "req", "id": "c1", "method": "connect", "params": _connect_params()})
            res = ws.receive_json()
            assert res["type"] == "res"
            assert res["id"] == "c1"
            assert res["ok"] is True
            hello = res["payload"]
            assert hello["type"] == "hello-ok"
            assert int(hello["protocol"]) >= 1
            assert "snapshot" in hello and "policy" in hello
            assert "sessions.send" in list((hello.get("features") or {}).get("methods") or [])

    def test_ws_rejects_invalid_frame(self) -> None:
        with self.client.websocket_connect("/ws") as ws:
            ws.receive_json()  # connect.challenge
            ws.send_text("not-json")
            res = ws.receive_json()
            assert res["type"] == "res"
            assert res["ok"] is False

    def test_ws_connect_rejects_without_auth(self) -> None:
        with mock.patch("oclaw.interfaces.ws.runtime_impl.resolve_ws_auth_payload", return_value={}):
            with self.client.websocket_connect("/ws") as ws:
                ws.receive_json()
                bad = _connect_params()
                bad["auth"] = {}
                ws.send_json({"type": "req", "id": "c1", "method": "connect", "params": bad})
                res = None
                for _ in range(2):
                    msg = ws.receive_json()
                    if msg.get("type") == "res" and msg.get("id") == "c1":
                        res = msg
                        break
                assert res is not None
                assert res["type"] == "res"
                assert res["ok"] is False
                assert (res.get("error") or {}).get("code") == "UNAUTHORIZED"

    def test_ws_origin_blocked(self) -> None:
        with mock.patch("oclaw.interfaces.ws.runtime_impl.origin_is_allowed", return_value=False):
            with self.assertRaises(Exception):
                with self.client.websocket_connect("/ws", headers={"origin": "https://evil.example.com"}):
                    pass

    def test_ws_rate_limited(self) -> None:
        with mock.patch("oclaw.interfaces.ws.runtime_impl.WS_RATE_LIMIT_CONN_PER_WINDOW", 1):
            with self.client.websocket_connect("/ws") as ws:
                ws.receive_json()
                ws.send_json({"type": "req", "id": "c1", "method": "connect", "params": _connect_params()})
                ws.receive_json()
                ws.send_json({"type": "req", "id": "r1", "method": "sessions.list", "params": {}})
                first = None
                for _ in range(8):
                    msg = ws.receive_json()
                    if msg.get("type") == "res" and msg.get("id") == "r1":
                        first = msg
                        break
                assert first is not None
                assert first["ok"] is True
                ws.send_json({"type": "req", "id": "r2", "method": "sessions.list", "params": {}})
                second = None
                for _ in range(8):
                    msg = ws.receive_json()
                    if msg.get("type") == "res" and msg.get("id") == "r2":
                        second = msg
                        break
                assert second is not None
                assert second["ok"] is False
                assert (second.get("error") or {}).get("code") == "RATE_LIMITED"

    def test_ws_agent_run_emits_events_and_response(self) -> None:
        def _fake_handle_turn(self, **kwargs):  # noqa: ANN001
            on_progress = kwargs.get("on_progress")
            on_token = kwargs.get("on_token")
            on_tool_ui = kwargs.get("on_tool_ui")
            rid = kwargs.get("run_id") or "run_test"
            if callable(on_progress):
                on_progress("oclaw: think (1)…")
            if callable(on_tool_ui):
                on_tool_ui("skill", {"ok": True})
            if callable(on_token):
                on_token("hello")
            return OclawGatewayResult(
                run_id=str(rid),
                reply_text="done",
                trace_id="trace_test",
                elapsed_ms=5,
                mode="sync_direct",
                task_id=None,
                selected_specialist="generalist",
                interaction_mode="comprehensive",
            )

        with mock.patch("oclaw.runtime.gateway.OclawGateway.handle_turn", new=_fake_handle_turn):
            with self.client.websocket_connect("/ws") as ws:
                ws.receive_json()  # connect.challenge
                ws.send_json({"type": "req", "id": "c1", "method": "connect", "params": _connect_params()})
                ws.receive_json()

                ws.send_json(
                    {
                        "type": "req",
                        "id": "a1",
                        "method": "agent",
                        "params": {"message": "hi", "idempotencyKey": "k", "sessionId": "sess1"},
                    }
                )
                # Events may race ahead of the response; drain until we see res(id=a1).
                res = None
                for _ in range(10):
                    msg = ws.receive_json()
                    if msg.get("type") == "res" and msg.get("id") == "a1":
                        res = msg
                        break
                assert res is not None
                assert res["ok"] is True
                payload = res["payload"]
                assert payload["runId"]

                # We should see at least one agent.event (token/progress/tool) and the terminal end.
                seen_agent_event = False
                seen_end = False
                for _ in range(6):
                    msg = ws.receive_json()
                    if msg.get("type") != "event":
                        continue
                    if msg.get("event") != "agent.event":
                        continue
                    seen_agent_event = True
                    data = (msg.get("payload") or {}).get("data") or {}
                    if data.get("phase") == "end":
                        seen_end = True
                        break
                assert seen_agent_event is True
                assert seen_end is True

    def test_ws_sessions_send_routes_to_agent_flow(self) -> None:
        def _fake_handle_turn(self, **kwargs):  # noqa: ANN001
            rid = kwargs.get("run_id") or "run_test"
            return OclawGatewayResult(
                run_id=str(rid),
                reply_text="done",
                trace_id="trace_sessions_send",
                elapsed_ms=7,
                mode="sync_direct",
                task_id=None,
                selected_specialist="generalist",
                interaction_mode="comprehensive",
            )

        with mock.patch("oclaw.runtime.gateway.OclawGateway.handle_turn", new=_fake_handle_turn):
            with self.client.websocket_connect("/ws") as ws:
                ws.receive_json()
                ws.send_json({"type": "req", "id": "c1", "method": "connect", "params": _connect_params()})
                ws.receive_json()
                ws.send_json(
                    {
                        "type": "req",
                        "id": "s1",
                        "method": "sessions.send",
                        "params": {"key": "sessX", "message": "hello from sessions", "idempotencyKey": "idem1"},
                    }
                )
                res = None
                for _ in range(10):
                    msg = ws.receive_json()
                    if msg.get("type") == "res" and msg.get("id") == "s1":
                        res = msg
                        break
                assert res is not None
                assert res["ok"] is True
                assert str((res.get("payload") or {}).get("runId") or "").strip() != ""

    def test_ws_agent_run_alias_works(self) -> None:
        def _fake_handle_turn(self, **kwargs):  # noqa: ANN001
            rid = kwargs.get("run_id") or "run_alias"
            return OclawGatewayResult(
                run_id=str(rid),
                reply_text="ok",
                trace_id="trace_alias",
                elapsed_ms=2,
                mode="sync_direct",
                task_id=None,
                selected_specialist="generalist",
                interaction_mode="comprehensive",
            )

        with mock.patch("oclaw.runtime.gateway.OclawGateway.handle_turn", new=_fake_handle_turn):
            with self.client.websocket_connect("/ws") as ws:
                ws.receive_json()
                ws.send_json({"type": "req", "id": "c1", "method": "connect", "params": _connect_params()})
                hello = ws.receive_json()
                methods = list(((hello.get("payload") or {}).get("features") or {}).get("methods") or [])
                assert "agent.run" in methods
                ws.send_json(
                    {
                        "type": "req",
                        "id": "r1",
                        "method": "agent.run",
                        "params": {"message": "alias", "idempotencyKey": "idem_alias", "sessionId": "sessAlias"},
                    }
                )
                res = None
                for _ in range(10):
                    msg = ws.receive_json()
                    if msg.get("type") == "res" and msg.get("id") == "r1":
                        res = msg
                        break
                assert res is not None
                assert res["ok"] is True

    def test_ws_chat_send_ack_then_final_event(self) -> None:
        def _fake_handle_turn(self, **kwargs):  # noqa: ANN001
            rid = kwargs.get("run_id") or "run_chat_send"
            on_token = kwargs.get("on_token")
            if callable(on_token):
                on_token("he")
                on_token("llo")
            return OclawGatewayResult(
                run_id=str(rid),
                reply_text="hello",
                trace_id="trace_chat_send",
                elapsed_ms=3,
                mode="sync_direct",
                task_id=None,
                selected_specialist="generalist",
                interaction_mode="comprehensive",
            )

        with mock.patch("oclaw.runtime.gateway.OclawGateway.handle_turn", new=_fake_handle_turn):
            with self.client.websocket_connect("/ws") as ws:
                ws.receive_json()
                ws.send_json({"type": "req", "id": "c1", "method": "connect", "params": _connect_params()})
                ws.receive_json()

                ws.send_json(
                    {
                        "type": "req",
                        "id": "cs1",
                        "method": "chat.send",
                        "params": {
                            "sessionKey": "sess-chat",
                            "message": "hi",
                            "idempotencyKey": "idem-chat-1",
                            "execution_mode": "plan",
                        },
                    }
                )
                ack = None
                for _ in range(12):
                    msg = ws.receive_json()
                    if msg.get("type") == "res" and msg.get("id") == "cs1":
                        ack = msg
                        break
                assert ack is not None
                assert ack.get("type") == "res"
                assert ack.get("id") == "cs1"
                assert ack.get("ok") is True
                assert str((ack.get("payload") or {}).get("status") or "") == "started"
                assert str((ack.get("payload") or {}).get("executionMode") or "") == "plan"
                run_id = str((ack.get("payload") or {}).get("runId") or "")
                assert run_id.strip() != ""

                seen_final = False
                for _ in range(12):
                    msg = ws.receive_json()
                    if msg.get("type") != "event":
                        continue
                    if msg.get("event") != "chat":
                        continue
                    payload = msg.get("payload") or {}
                    if str(payload.get("runId") or "") != run_id:
                        continue
                    if str(payload.get("state") or "") == "final":
                        seen_final = True
                        break
                assert seen_final is True

    def test_ws_chat_send_emits_delta_and_session_tool(self) -> None:
        def _fake_handle_turn(self, **kwargs):  # noqa: ANN001
            rid = kwargs.get("run_id") or "run_chat_send_stream"
            on_token = kwargs.get("on_token")
            on_tool_ui = kwargs.get("on_tool_ui")
            if callable(on_tool_ui):
                on_tool_ui("skill", {"ok": True})
            if callable(on_token):
                on_token("Hel")
                on_token("lo")
            return OclawGatewayResult(
                run_id=str(rid),
                reply_text="Hello",
                trace_id="trace_chat_send_stream",
                elapsed_ms=3,
                mode="sync_direct",
                task_id=None,
                selected_specialist="generalist",
                interaction_mode="comprehensive",
            )

        with mock.patch("oclaw.runtime.gateway.OclawGateway.handle_turn", new=_fake_handle_turn):
            with self.client.websocket_connect("/ws") as ws:
                ws.receive_json()
                ws.send_json({"type": "req", "id": "c1", "method": "connect", "params": _connect_params()})
                ws.receive_json()

                ws.send_json(
                    {
                        "type": "req",
                        "id": "cs2",
                        "method": "chat.send",
                        "params": {"sessionKey": "sess-chat2", "message": "hi", "idempotencyKey": "idem-chat-2"},
                    }
                )
                ack = None
                for _ in range(12):
                    msg = ws.receive_json()
                    if msg.get("type") == "res" and msg.get("id") == "cs2":
                        ack = msg
                        break
                assert ack is not None
                assert ack.get("type") == "res"
                assert ack.get("id") == "cs2"
                assert ack.get("ok") is True

                seen_delta = False
                seen_tool = False
                seen_final = False
                for _ in range(30):
                    msg = ws.receive_json()
                    if msg.get("type") != "event":
                        continue
                    if msg.get("event") == "session.tool":
                        seen_tool = True
                    if msg.get("event") != "chat":
                        continue
                    payload = msg.get("payload") or {}
                    st = str(payload.get("state") or "")
                    if st == "delta":
                        seen_delta = True
                    if st == "final":
                        seen_final = True
                        break
                assert seen_delta is True
                assert seen_tool is True
                assert seen_final is True

    def test_ws_replay_events_with_last_seq(self) -> None:
        def _fake_handle_turn(self, **kwargs):  # noqa: ANN001
            rid = kwargs.get("run_id") or "run_replay"
            on_token = kwargs.get("on_token")
            if callable(on_token):
                on_token("re")
                on_token("play")
            return OclawGatewayResult(
                run_id=str(rid),
                reply_text="replay",
                trace_id="trace_replay",
                elapsed_ms=3,
                mode="sync_direct",
                task_id=None,
                selected_specialist="generalist",
                interaction_mode="comprehensive",
            )

        with mock.patch("oclaw.runtime.gateway.OclawGateway.handle_turn", new=_fake_handle_turn):
            with self.client.websocket_connect("/ws") as ws1:
                ws1.receive_json()
                ws1.send_json({"type": "req", "id": "c1", "method": "connect", "params": _connect_params()})
                ws1.receive_json()
                ws1.send_json(
                    {
                        "type": "req",
                        "id": "cs1",
                        "method": "chat.send",
                        "params": {"sessionKey": "sess-replay", "message": "hi", "idempotencyKey": "idem-replay-1"},
                    }
                )
                seq_seen = 0
                for _ in range(20):
                    msg = ws1.receive_json()
                    if msg.get("type") != "event":
                        continue
                    seq_seen = max(seq_seen, int(msg.get("seq") or 0))
                    if msg.get("event") == "chat" and str((msg.get("payload") or {}).get("state") or "") == "final":
                        break
                assert seq_seen > 0

            p = _connect_params()
            p["lastSeq"] = max(0, seq_seen - 1)
            with self.client.websocket_connect("/ws") as ws2:
                ws2.receive_json()
                ws2.send_json({"type": "req", "id": "c2", "method": "connect", "params": p})
                ws2.receive_json()
                replayed = False
                for _ in range(8):
                    msg = ws2.receive_json()
                    if msg.get("type") != "event":
                        continue
                    if int(msg.get("seq") or 0) > int(p["lastSeq"]):
                        replayed = True
                        break
                assert replayed is True

