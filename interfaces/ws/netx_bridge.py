from __future__ import annotations

import hmac
import json
import os
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from svc.persistence.assistant_store import get_assistant_store


def _bridge_token_expected() -> str:
    return str(os.getenv("OCLAW_OPS_AI_SHARED_TOKEN") or "").strip()


def _verify_bridge_token(token: str) -> bool:
    expected = _bridge_token_expected()
    if not expected:
        return False
    got = str(token or "").strip()
    if not got:
        return False
    return hmac.compare_digest(expected, got)


def _default_whatsapp_account_id() -> str:
    return str(os.getenv("AIA_WHATSAPP_ACCOUNT_ID") or "wa-default").strip()


def _default_tenant_id() -> str:
    return str(os.getenv("OCLAW_DEFAULT_TENANT_ID") or "default").strip()


def _format_alarm_text(payload: dict[str, Any]) -> str:
    action = str(payload.get("action") or "").strip().lower()
    label = str(payload.get("rule_label") or payload.get("native_probable_cause") or "Key alarm").strip()
    ne = payload.get("ne") if isinstance(payload.get("ne"), dict) else {}
    host = str(ne.get("host_name") or payload.get("host_name") or "").strip()
    ip = str(ne.get("ip_address") or "").strip()
    ne_name = str(ne.get("ne_name") or ne.get("user_label") or "").strip()
    device = host or ne_name or str(payload.get("ne_id") or "").strip()
    if ip:
        device = f"{device} ({ip})" if device else ip
    action_label = {
        "inserted": "Alarm Raised",
        "updated": "Alarm Updated",
        "deleted": "Alarm Cleared",
    }.get(action, action or "Alarm")
    lines = [
        f"[UME {action_label}] {label}",
        f"Device: {device or '-'}",
        f"Object: {str(payload.get('object_name') or '-').strip()}",
        f"Severity: {str(payload.get('perceived_severity') or '-').strip()}",
        f"Cause: {str(payload.get('native_probable_cause') or '-').strip()}",
        f"Time: {str(payload.get('time_created') or '-').strip()}",
        f"notificationId: {str(payload.get('notification_id') or '-').strip()}",
    ]
    return "\n".join(lines)


def handle_netx_alarm_event(payload: dict[str, Any]) -> dict[str, Any]:
    store = get_assistant_store()
    tenant_id = _default_tenant_id()
    account_id = _default_whatsapp_account_id()
    binding = store.get_whatsapp_alert_binding(tenant_id=tenant_id, account_id=account_id)
    if not binding or not bool(binding.get("enabled")):
        return {"ok": False, "error": "whatsapp_alert_binding_missing"}
    group_jid = str(binding.get("group_jid") or "").strip()
    if not group_jid:
        return {"ok": False, "error": "group_jid_missing"}
    text = _format_alarm_text(payload)
    msg_id = store.enqueue_channel_outbound_message(
        channel="whatsapp",
        chat_id=group_jid,
        text=text,
        tenant_id=tenant_id,
        account_id=account_id,
        source="netx.alarm",
    )
    return {"ok": True, "outbound_id": msg_id, "chat_id": group_jid}


async def netx_bridge_loop(ws: WebSocket) -> None:
    await ws.accept()
    authed = False
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                await ws.send_json({"type": "error", "error": "invalid_json"})
                continue
            if not isinstance(msg, dict):
                await ws.send_json({"type": "error", "error": "invalid_message"})
                continue
            mtype = str(msg.get("type") or "").strip().lower()
            if not authed:
                if mtype != "auth":
                    await ws.send_json({"type": "auth-fail", "error": "auth_required"})
                    await ws.close(code=4401)
                    return
                token = str(msg.get("token") or "").strip()
                if not _verify_bridge_token(token):
                    await ws.send_json({"type": "auth-fail", "error": "invalid_token"})
                    await ws.close(code=4401)
                    return
                authed = True
                await ws.send_json({"type": "auth-ok"})
                continue
            if mtype == "ping":
                await ws.send_json({"type": "pong"})
                continue
            if mtype == "event" and str(msg.get("event") or "").strip() == "netx.alarm":
                payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
                alarm_key = str(payload.get("alarm_key") or "").strip()
                try:
                    out = handle_netx_alarm_event(payload)
                    await ws.send_json(
                        {
                            "type": "ack",
                            "alarm_key": alarm_key,
                            "ok": bool(out.get("ok")),
                            "error": str(out.get("error") or ""),
                            "outbound_id": str(out.get("outbound_id") or ""),
                        }
                    )
                except Exception as exc:
                    await ws.send_json(
                        {
                            "type": "ack",
                            "alarm_key": alarm_key,
                            "ok": False,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                continue
            await ws.send_json({"type": "error", "error": f"unknown_type:{mtype}"})
    except WebSocketDisconnect:
        return
