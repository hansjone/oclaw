from __future__ import annotations

import asyncio
import os
import secrets
import threading
import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from oclaw.runtime.application.gateway import process_inbound_payload_usecase


router = APIRouter()


def _require_ilink_auth(
    *,
    authorization_type: str | None,
    authorization: str | None,
) -> str:
    # Minimal contract required by oclaw-weixin:
    # - AuthorizationType: ilink_bot_token
    # - Authorization: Bearer <token>
    if (authorization_type or "").strip() != "ilink_bot_token":
        raise HTTPException(status_code=401, detail="invalid AuthorizationType")
    auth = (authorization or "").strip()
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="empty bearer token")
    expected = str(os.getenv("AIA_ILINK_BOT_TOKEN") or "").strip()
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="invalid bearer token")
    return token


def _now_ms() -> int:
    return int(time.time() * 1000)


def _normalize_channel(raw: Any) -> str:
    ch = str(raw or "wechat").strip().lower()
    return ch if ch else "wechat"


def _resolve_account_id(obj: dict[str, Any]) -> str:
    for key in ("account_id", "bot_id", "aibotid", "app_id", "agent_id"):
        val = obj.get(key)
        if val:
            return str(val).strip()
    return ""


def _resolve_stream_selector(body: dict[str, Any]) -> tuple[str, str]:
    return _normalize_channel(body.get("channel")), _resolve_account_id(body)


def _extract_text_from_body(body: dict[str, Any]) -> str:
    direct = body.get("text")
    if isinstance(direct, str):
        return direct.strip()
    content = body.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text.strip()
    msg = body.get("msg")
    if isinstance(msg, dict):
        text = msg.get("text")
        if isinstance(text, str):
            return text.strip()
        nested = msg.get("content")
        if isinstance(nested, str):
            return nested.strip()
        if isinstance(nested, dict):
            text2 = nested.get("text")
            if isinstance(text2, str):
                return text2.strip()
    return ""


def _extract_inbound_identity(body: dict[str, Any]) -> tuple[str, str]:
    chat_cands = (
        body.get("chat_id"),
        body.get("room_id"),
        body.get("conversation_id"),
        body.get("external_chat_id"),
        body.get("to_wxid"),
    )
    user_cands = (
        body.get("user_id"),
        body.get("external_user_id"),
        body.get("from_user"),
        body.get("from_wxid"),
        body.get("sender"),
        body.get("wxid"),
    )
    msg = body.get("msg")
    if isinstance(msg, dict):
        chat_cands = chat_cands + (
            msg.get("chat_id"),
            msg.get("room_id"),
            msg.get("conversation_id"),
            msg.get("to_wxid"),
        )
        user_cands = user_cands + (
            msg.get("user_id"),
            msg.get("external_user_id"),
            msg.get("from_user"),
            msg.get("from_wxid"),
            msg.get("sender"),
            msg.get("wxid"),
        )
    user_id = next((str(v).strip() for v in user_cands if str(v or "").strip()), "")
    chat_id = next((str(v).strip() for v in chat_cands if str(v or "").strip()), "")
    if not chat_id:
        chat_id = user_id
    return user_id, chat_id


class _IlinkBridge:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seq = 0
        self._events: list[dict[str, Any]] = []

    def enqueue_reply(
        self,
        *,
        token: str,
        channel: str,
        account_id: str,
        chat_id: str,
        text: str,
        context_token: str | None,
    ) -> None:
        payload = {
            "channel": channel,
            "account_id": account_id,
            "chat_id": chat_id,
            "text": text,
            "content": {"type": "text", "text": text},
            # Required by iLink sendmessage protocol; we cache it per reply so the
            # bridge can recover across restarts without needing in-memory token cache.
            "context_token": (context_token or "").strip(),
            "ts": _now_ms(),
        }
        with self._lock:
            self._seq += 1
            event = {
                "id": self._seq,
                "token": token,
                "payload": payload,
            }
            self._events.append(event)
            if len(self._events) > 2000:
                self._events = self._events[-1000:]

    def poll(
        self,
        *,
        token: str,
        cursor: int,
        channel: str,
        account_id: str,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        out: list[dict[str, Any]] = []
        next_cursor = max(0, int(cursor or 0))
        with self._lock:
            for event in self._events:
                eid = int(event.get("id") or 0)
                if eid <= cursor:
                    continue
                if str(event.get("token") or "") != token:
                    continue
                payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
                if channel and str(payload.get("channel") or "") != channel:
                    continue
                if account_id and str(payload.get("account_id") or "") != account_id:
                    continue
                next_cursor = max(next_cursor, eid)
                item = dict(payload)
                item["id"] = str(eid)
                item["msg_id"] = str(eid)
                out.append(item)
                if len(out) >= max(1, limit):
                    break
        return out, next_cursor


_BRIDGE = _IlinkBridge()


async def _process_inbound_and_enqueue(
    *,
    token: str,
    channel: str,
    account_id: str,
    user_id: str,
    chat_id: str,
    payload: dict[str, Any],
) -> None:
    def _extract_context_token(in_payload: dict[str, Any]) -> str:
        meta = in_payload.get("metadata")
        raw = {}
        if isinstance(meta, dict):
            raw = meta.get("raw") if isinstance(meta.get("raw"), dict) else {}
        if not isinstance(raw, dict):
            raw = {}

        # 1) Most direct: raw.msg.context_token (when runner forwards the original msg object).
        msg = raw.get("msg")
        if isinstance(msg, dict):
            ctx = msg.get("context_token")
            if ctx is not None:
                return str(ctx).strip()

        # 2) Runner also sets raw.metadata.context_token.
        raw_meta = raw.get("metadata")
        if isinstance(raw_meta, dict):
            ctx2 = raw_meta.get("context_token")
            if ctx2 is not None:
                return str(ctx2).strip()

        # 3) Some clients may put it at top-level.
        top_ctx = raw.get("context_token")
        if top_ctx is not None:
            return str(top_ctx).strip()

        return ""

    try:
        out = await asyncio.wait_for(asyncio.to_thread(process_inbound_payload_usecase, payload), timeout=60.0)
    except asyncio.TimeoutError:
        ctx_token = _extract_context_token(payload)
        _BRIDGE.enqueue_reply(
            token=token,
            channel=channel,
            account_id=account_id,
            chat_id=chat_id or user_id,
            text="系统繁忙，处理超时，请稍后重试。",
            context_token=ctx_token,
        )
        return
    except Exception as exc:
        ctx_token = _extract_context_token(payload)
        _BRIDGE.enqueue_reply(
            token=token,
            channel=channel,
            account_id=account_id,
            chat_id=chat_id or user_id,
            text=f"系统错误：{type(exc).__name__}",
            context_token=ctx_token,
        )
        return

    replies = out.get("replies") if isinstance(out, dict) else []
    if not isinstance(replies, list):
        return
    for item in replies:
        if not isinstance(item, dict):
            continue
        ctx_token = _extract_context_token(payload)
        reply_text = str(item.get("text") or "").strip()
        reply_chat_id = str(item.get("chat_id") or chat_id or user_id).strip() or user_id
        if not reply_text:
            continue
        _BRIDGE.enqueue_reply(
            token=token,
            channel=channel,
            account_id=account_id,
            chat_id=reply_chat_id,
            text=reply_text,
            context_token=ctx_token,
        )


@router.post("/ilink/bot/getupdates")
async def ilink_getupdates(
    body: dict[str, Any],
    request: Request,
    authorizationtype: str | None = Header(default=None, alias="AuthorizationType"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    token = _require_ilink_auth(authorization_type=authorizationtype, authorization=authorization)
    buf = str(body.get("get_updates_buf") or "")
    try:
        cursor = int(buf or "0")
    except Exception:
        cursor = 0
    channel, account_id = _resolve_stream_selector(body)
    limit_raw = body.get("limit")
    try:
        limit = max(1, min(int(limit_raw), 100))
    except Exception:
        limit = 50
    timeout_raw = body.get("longpolling_timeout_ms")
    try:
        timeout_ms = max(1000, min(int(timeout_raw), 35_000))
    except Exception:
        timeout_ms = 35_000
    deadline = time.time() + (timeout_ms / 1000.0)
    msgs: list[dict[str, Any]] = []
    next_cursor = cursor
    while time.time() < deadline:
        msgs, next_cursor = _BRIDGE.poll(
            token=token,
            cursor=cursor,
            channel=channel,
            account_id=account_id,
            limit=limit,
        )
        if msgs:
            break
        await asyncio.sleep(0.2)
    if not msgs:
        msgs, next_cursor = _BRIDGE.poll(
            token=token,
            cursor=cursor,
            channel=channel,
            account_id=account_id,
            limit=limit,
        )
    _ = request
    return {
        "ret": 0,
        "msgs": msgs,
        "get_updates_buf": str(next_cursor if msgs else cursor),
        "longpolling_timeout_ms": timeout_ms,
    }


@router.post("/ilink/bot/sendmessage")
async def ilink_sendmessage(
    body: dict[str, Any],
    authorizationtype: str | None = Header(default=None, alias="AuthorizationType"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    token = _require_ilink_auth(authorization_type=authorizationtype, authorization=authorization)
    channel, account_id = _resolve_stream_selector(body)
    user_id, chat_id = _extract_inbound_identity(body)
    text = _extract_text_from_body(body)
    if not user_id:
        return {"ret": 400, "errmsg": "missing user_id"}
    if not account_id:
        return {"ret": 400, "errmsg": "missing account_id"}
    payload = {
        "channel": channel,
        "account_id": account_id,
        "user_id": user_id,
        "chat_id": chat_id,
        "text": text,
        "metadata": {"source": "ilink", "raw": body},
    }
    asyncio.create_task(
        _process_inbound_and_enqueue(
            token=token,
            channel=channel,
            account_id=account_id,
            user_id=user_id,
            chat_id=chat_id,
            payload=payload,
        )
    )
    return {"ret": 0}


@router.post("/ilink/bot/getuploadurl")
async def ilink_getuploadurl(
    body: dict[str, Any],
    authorizationtype: str | None = Header(default=None, alias="AuthorizationType"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    _require_ilink_auth(authorization_type=authorizationtype, authorization=authorization)
    # TODO: implement AES-128-ECB upload flow + pre-signed URL integration.
    _ = body
    return {"ret": 0, "upload_param": "", "thumb_upload_param": ""}


@router.post("/ilink/bot/getconfig")
async def ilink_getconfig(
    body: dict[str, Any],
    authorizationtype: str | None = Header(default=None, alias="AuthorizationType"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    _require_ilink_auth(authorization_type=authorizationtype, authorization=authorization)
    _ = body
    # typing_ticket is required by sendtyping; we return a stable random-like token per request for now.
    return {"ret": 0, "typing_ticket": secrets.token_urlsafe(24)}


@router.post("/ilink/bot/sendtyping")
async def ilink_sendtyping(
    body: dict[str, Any],
    authorizationtype: str | None = Header(default=None, alias="AuthorizationType"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    _require_ilink_auth(authorization_type=authorizationtype, authorization=authorization)
    _ = body
    return {"ret": 0}


__all__ = ["router"]

