from __future__ import annotations

import secrets
import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request


router = APIRouter()


def _require_ilink_auth(
    *,
    authorization_type: str | None,
    authorization: str | None,
) -> None:
    # Minimal contract required by openclaw-weixin:
    # - AuthorizationType: ilink_bot_token
    # - Authorization: Bearer <token>
    if (authorization_type or "").strip() != "ilink_bot_token":
        raise HTTPException(status_code=401, detail="invalid AuthorizationType")
    auth = (authorization or "").strip()
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")


def _now_ms() -> int:
    return int(time.time() * 1000)


@router.post("/ilink/bot/getupdates")
async def ilink_getupdates(
    body: dict[str, Any],
    request: Request,
    authorizationtype: str | None = Header(default=None, alias="AuthorizationType"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    _require_ilink_auth(authorization_type=authorizationtype, authorization=authorization)
    # TODO: implement real long-poll cursor + message queue.
    # For now, return an empty poll result so the plugin can stay connected.
    buf = str(body.get("get_updates_buf") or "")
    _ = request
    return {"ret": 0, "msgs": [], "get_updates_buf": buf, "longpolling_timeout_ms": 35000}


@router.post("/ilink/bot/sendmessage")
async def ilink_sendmessage(
    body: dict[str, Any],
    authorizationtype: str | None = Header(default=None, alias="AuthorizationType"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    _require_ilink_auth(authorization_type=authorizationtype, authorization=authorization)
    # TODO: map outbound message into our channel sender (when implemented).
    _ = body
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

