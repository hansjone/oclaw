from __future__ import annotations

import hashlib
import re
from typing import Any

from interfaces.channels.base import InboundMessage, OutboundMessage
from interfaces.channels.wecom.wecom_bridge import WeComAdapter
from runtime.types import normalize_interaction_mode, normalize_requested_specialist

_CHANNEL_DISPATCH_INTERACTION_KEY_PREFIX = "channel.dispatch.interaction_mode."
_CHANNEL_DISPATCH_SPECIALIST_KEY_PREFIX = "channel.dispatch.specialist."


def _channel_dispatch_interaction_key(channel: str) -> str:
    return f"{_CHANNEL_DISPATCH_INTERACTION_KEY_PREFIX}{str(channel or '').strip().lower()}"


def _channel_dispatch_specialist_key(channel: str) -> str:
    return f"{_CHANNEL_DISPATCH_SPECIALIST_KEY_PREFIX}{str(channel or '').strip().lower()}"


def _resolve_channel_dispatch(store: Any, *, channel: str, account: dict[str, Any] | None) -> tuple[str, str]:
    ch = str(channel or "").strip().lower()
    interaction_mode = normalize_interaction_mode(store.get_setting(_channel_dispatch_interaction_key(ch)) or "expert")
    specialist = normalize_requested_specialist(store.get_setting(_channel_dispatch_specialist_key(ch)) or "generalist")
    cfg = (account or {}).get("config")
    if isinstance(cfg, dict):
        cfg_mode = cfg.get("interaction_mode")
        cfg_specialist = cfg.get("specialist")
        if cfg_mode is not None:
            interaction_mode = normalize_interaction_mode(cfg_mode)
        if cfg_specialist is not None:
            specialist = normalize_requested_specialist(cfg_specialist)
    return interaction_mode, specialist


def _build_admin_gateway_executor(store: Any, *, tenant_id: str, specialist: str, session_id: str) -> Any:
    from runtime.agents.factory import build_gateway_executor

    return build_gateway_executor(
        store,
        lang="zh",
        specialist=specialist,
        viewer_user_id=None,
        viewer_username="administrator",
        viewer_tenant_id=(tenant_id or None),
        policy_session_id=session_id,
        path_policy_tenant_id=(tenant_id or None),
        path_policy_user_id=None,
    )


def _menu_text() -> str:
    return (
        "已绑定成功，常用命令：\n"
        "1) 帮助 / 菜单\n"
        "2) 记待办 <内容>\n"
        "3) 查待办\n"
        "4) 完成待办 <todo_id>\n"
        "5) 指派待办 <todo_id> <assignee_user_id>\n"
        "6) 加知识 <内容>\n"
        "7) 查知识 <关键词>"
    )


def _handle_productivity_commands(*, text: str, tenant_id: str, user_id: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return None
    if t in ("帮助", "菜单", "help", "/help"):
        return _menu_text()

    from svc.config.paths import db_path
    from svc.persistence.sqlite_store import SqliteStore

    store = SqliteStore(db_path())

    if t.startswith("记待办 "):
        title = t[len("记待办 ") :].strip()
        if not title:
            return "待办内容不能为空。示例：记待办 明天10点开会"
        row = store.todo_create(tenant_id=tenant_id, owner_user_id=user_id, title=title)
        return f"已创建待办：{row['id'][:8]} | {row['title']}"

    if t in ("查待办", "todo", "todos"):
        rows = store.todo_list(tenant_id=tenant_id, assignee_user_id=None, status="open", limit=10)
        if not rows:
            return "当前没有未完成待办。"
        lines = [f"- {r['id'][:8]} | {r['title']}" for r in rows]
        return "未完成待办：\n" + "\n".join(lines)

    if t.startswith("完成待办 "):
        tid = t[len("完成待办 ") :].strip()
        if not tid:
            return "请提供 todo_id。示例：完成待办 1234abcd"
        rows = store.todo_list(tenant_id=tenant_id, assignee_user_id=None, status=None, limit=200)
        full = next((r["id"] for r in rows if str(r["id"]).startswith(tid)), tid)
        ok = store.todo_set_status(tenant_id=tenant_id, todo_id=full, status="done")
        return "已完成。" if ok else "未找到该待办。"

    if t.startswith("指派待办 "):
        body = t[len("指派待办 ") :].strip()
        parts = body.split()
        if len(parts) < 2:
            return "格式：指派待办 <todo_id> <assignee_user_id>"
        tid, assignee = parts[0], parts[1]
        rows = store.todo_list(tenant_id=tenant_id, assignee_user_id=None, status=None, limit=200)
        full = next((r["id"] for r in rows if str(r["id"]).startswith(tid)), tid)
        ok = store.todo_assign(tenant_id=tenant_id, todo_id=full, assignee_user_id=assignee)
        return "已指派。" if ok else "未找到该待办或用户。"

    if t.startswith("加知识 "):
        content = t[len("加知识 ") :].strip()
        if not content:
            return "知识内容不能为空。示例：加知识 办公室WiFi密码是12345678"
        from runtime.tools.experts.productivity.kb_tools import kb_add_tool

        res = kb_add_tool().handler({"tenant_id": tenant_id, "user_id": user_id, "text": content})
        if not res.get("ok"):
            return f"写入失败：{res.get('error')}"
        return f"已写入知识：{str(res.get('chunk_id') or '')[:8]}"

    if t.startswith("查知识 "):
        q = t[len("查知识 ") :].strip()
        if not q:
            return "请提供关键词。示例：查知识 WiFi 密码"
        from runtime.tools.experts.productivity.kb_tools import kb_search_tool

        res = kb_search_tool().handler({"tenant_id": tenant_id, "query": q, "limit": 5})
        if not res.get("ok"):
            return f"查询失败：{res.get('error')}"
        hits = res.get("hits") if isinstance(res.get("hits"), list) else []
        if not hits:
            return "未找到相关知识。"
        lines = [f"- {str(h.get('source') or '')}: {str(h.get('snippet') or '')}" for h in hits[:5] if isinstance(h, dict)]
        return "知识检索结果：\n" + "\n".join(lines)

    return None


def _role_can_write(role: str, text: str) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return True
    if role in ("owner", "admin", "member"):
        return True
    write_prefixes = ("记待办 ", "完成待办 ", "指派待办 ", "加知识 ")
    return not any((text or "").startswith(p) for p in write_prefixes)


def _resolve_wecom_account_id(inbound: Any, payload: dict[str, Any]) -> str:
    if isinstance(inbound.metadata, dict):
        for key in ("aibotid", "bot_id", "account_id"):
            val = inbound.metadata.get(key)
            if val:
                return str(val).strip()
        raw = inbound.metadata.get("raw")
        if isinstance(raw, dict):
            for key in ("aibotid", "bot_id", "account_id"):
                val = raw.get(key)
                if val:
                    return str(val).strip()
    for key in ("aibotid", "bot_id", "account_id"):
        val = payload.get(key)
        if val:
            return str(val).strip()
    raw_payload = payload.get("raw")
    if isinstance(raw_payload, dict) and raw_payload.get("aibotid"):
        return str(raw_payload.get("aibotid")).strip()
    return ""


def _resolve_generic_account_id(inbound: InboundMessage, payload: dict[str, Any]) -> str:
    if isinstance(inbound.metadata, dict):
        for key in ("account_id", "bot_id", "app_id", "agent_id"):
            val = inbound.metadata.get(key)
            if val:
                return str(val).strip()
    for key in ("account_id", "bot_id", "app_id", "agent_id"):
        val = payload.get(key)
        if val:
            return str(val).strip()
    raw_payload = payload.get("raw")
    if isinstance(raw_payload, dict):
        for key in ("account_id", "bot_id", "app_id", "agent_id"):
            val = raw_payload.get(key)
            if val:
                return str(val).strip()
    return ""


def _ensure_administrator_owner(store: Any) -> dict[str, Any] | None:
    tenant_name = str(store.get_setting("wecom_auto_bind_tenant_name") or "Team").strip() or "Team"
    tenants = store.list_tenants(limit=200)
    tenant = next((t for t in tenants if str(t.get("name") or "") == tenant_name), None)
    if tenant is None:
        tenant = store.create_tenant(tenant_name)
    tenant_id = str(tenant.get("id") or "")
    if not tenant_id:
        return None
    user = store.get_user_by_username(tenant_id=tenant_id, username="administrator")
    if not user:
        try:
            from svc.config.passwords import load_expected_password
        except Exception:
            load_expected_password = None  # type: ignore
        pwd = load_expected_password(store) if callable(load_expected_password) else None
        if not pwd:
            return None
        user = store.create_user_account(
            tenant_id=tenant_id,
            username="administrator",
            password_hash=hashlib.sha256(pwd.encode("utf-8")).hexdigest(),
            display_name="Administrator",
            role="owner",
            is_active=True,
        )
    user_id = str((user or {}).get("id") or "")
    if not user_id:
        return None
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "display_name": (user or {}).get("display_name") or "Administrator",
        "role": str((user or {}).get("role") or "owner"),
    }


def _extract_group_name(inbound: Any) -> str:
    if not isinstance(inbound.metadata, dict):
        return ""
    cands: list[str] = []
    for key in ("chat_name", "group_name", "room_name", "conversation_name"):
        v = inbound.metadata.get(key)
        if v is not None:
            cands.append(str(v).strip())
    raw = inbound.metadata.get("raw")
    if isinstance(raw, dict):
        for key in ("chat_name", "group_name", "room_name", "conversation_name", "chatname"):
            v = raw.get(key)
            if v is not None:
                cands.append(str(v).strip())
        chat_obj = raw.get("chat")
        if isinstance(chat_obj, dict):
            for key in ("name", "chat_name", "group_name"):
                v = chat_obj.get(key)
                if v is not None:
                    cands.append(str(v).strip())
    for s in cands:
        if s:
            return s
    return ""


def _build_wecom_session_title(*, account_name: str, external_user_id: str, is_group: bool, group_name: str) -> str:
    base = f"{str(account_name or '').strip() or 'WeCom'}+{str(external_user_id or '').strip() or 'unknown'}"
    if is_group and str(group_name or "").strip():
        body = f"{base}+{str(group_name).strip()}"
    else:
        body = base
    return f"wechat|{body}"


def _build_channel_session_title(*, channel: str, account_name: str, external_user_id: str, is_group: bool, group_name: str) -> str:
    ch = str(channel or "").strip().lower() or "channel"
    if ch == "wecom":
        return _build_wecom_session_title(
            account_name=account_name,
            external_user_id=external_user_id,
            is_group=is_group,
            group_name=group_name,
        )
    base = f"{str(account_name or '').strip() or ch}+{str(external_user_id or '').strip() or 'unknown'}"
    body = f"{base}+{str(group_name or '').strip()}" if is_group and str(group_name or "").strip() else base
    return f"{ch}|{body}"


def _parse_generic_inbound(channel_name: str, payload: dict[str, Any]) -> InboundMessage:
    meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    user_id = str(payload.get("user_id") or payload.get("external_user_id") or "").strip()
    chat_id = str(payload.get("chat_id") or payload.get("external_chat_id") or user_id).strip()
    text = str(payload.get("text") or "").strip()
    if not user_id:
        raise ValueError("missing user_id")
    if not chat_id:
        chat_id = user_id
    is_group = bool(payload.get("is_group"))
    mentions = payload.get("mentions") if isinstance(payload.get("mentions"), list) else []
    attachments = payload.get("attachments") if isinstance(payload.get("attachments"), list) else []
    return InboundMessage(
        channel=str(channel_name or "unknown"),
        external_user_id=user_id,
        external_chat_id=chat_id,
        text=text,
        is_group=is_group,
        mentions=[str(x).strip() for x in mentions if str(x).strip()],
        attachments=[a for a in attachments if isinstance(a, dict)],
        metadata={str(k): v for k, v in meta.items()},
    )


def _parse_message_attachments(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    obj = raw
    if isinstance(raw, str):
        s = str(raw or "").strip()
        if not s:
            return []
        try:
            import json

            obj = json.loads(s)
        except Exception:
            return []
    if not isinstance(obj, list):
        return []
    return [x for x in obj if isinstance(x, dict)]


def _first_attachment_id(atts: list[dict[str, Any]]) -> str:
    for a in atts or []:
        if not isinstance(a, dict):
            continue
        aid = str(a.get("attachment_id") or a.get("attachmentId") or "").strip().lower()
        if aid:
            return aid
    return ""


def _collect_recent_tool_attachments(*, store: Any, session_id: str) -> list[dict[str, Any]]:
    """Fallback for channel delivery: if assistant attachments are missing, reuse recent tool attachments.

    This is intentionally conservative: only returns attachments when they look like media or refs.
    """
    sid = str(session_id or "").strip()
    if not sid:
        return []
    try:
        rows = store.get_messages(session_id=sid, limit=80)
    except Exception:
        rows = []
    # Prefer newest tool attachments.
    for row in reversed(list(rows or [])):
        role = str(getattr(row, "role", "") or "").strip().lower()
        if role != "tool":
            continue
        atts = _parse_message_attachments(getattr(row, "attachments", None))
        if not atts:
            continue
        # Only accept common media/ref shapes.
        ok = False
        for a in atts:
            if not isinstance(a, dict):
                continue
            t = str(a.get("type") or "").strip().lower()
            if t in {"image_ref", "video_ref", "binary_ref", "text_ref", "image", "input_image", "image_url"}:
                ok = True
                break
        if ok:
            return atts
    return []


def _maybe_add_media_path_for_wechat_reply(reply: dict[str, Any]) -> None:
    """For wechat/weixin sidecar, prefer a local file path for media send."""
    try:
        from svc.files.attachment_assets import AttachmentAssetStore
    except Exception:
        return
    if not isinstance(reply, dict):
        return
    if str(reply.get("media_path") or reply.get("mediaPath") or "").strip():
        return
    if str(reply.get("media_url") or reply.get("mediaUrl") or "").strip():
        return
    atts = reply.get("attachments") if isinstance(reply.get("attachments"), list) else []
    aid = _first_attachment_id([a for a in atts if isinstance(a, dict)])
    if not aid:
        return
    p = AttachmentAssetStore().get_local_path(aid)
    if not p:
        return
    # use the existing runner field name
    reply["media_path"] = str(p)


def _maybe_expand_reply_attachments_for_channel(reply: dict[str, Any]) -> None:
    """For chat sidecar delivery, convert attachment refs to base64 payloads.

    The runner supports base64 keys like data_base64/media_base64/image_base64/data.
    This avoids relying on sidecar being able to access gateway-local disk paths.
    """
    if not isinstance(reply, dict):
        return
    raw = reply.get("attachments")
    if not isinstance(raw, list) or not raw:
        return
    # If already has base64 payloads, keep as-is.
    for a in raw:
        if not isinstance(a, dict):
            continue
        if str(
            a.get("data_base64")
            or a.get("media_base64")
            or a.get("image_base64")
            or a.get("video_base64")
            or a.get("audio_base64")
            or a.get("data")
            or ""
        ).strip():
            return
    # Expand first attachment ref only (avoid large payload).
    a0 = next((a for a in raw if isinstance(a, dict)), None)
    if not isinstance(a0, dict):
        return
    aid = str(a0.get("attachment_id") or a0.get("attachmentId") or "").strip().lower()
    if not aid:
        return
    try:
        import base64

        from svc.files.attachment_assets import AttachmentAssetStore
    except Exception:
        return
    ast = AttachmentAssetStore()
    blob, meta = ast.load_bytes(aid)
    if not blob:
        return
    # Conservative cap to avoid blowing up channel payload.
    max_bytes = 8 * 1024 * 1024
    if len(blob) > max_bytes:
        return
    mime = (meta.mime if meta else "") or str(a0.get("mime") or a0.get("mime_type") or "application/octet-stream")
    name = (meta.name if meta else "") or str(a0.get("name") or "attachment")
    b64 = base64.b64encode(blob).decode("ascii")
    reply["attachments"] = [
        {
            "name": name,
            "mime": mime,
            "media_type": mime,
            "data_base64": b64,
        }
    ]


def _collect_reply_attachments_from_history(*, store: Any, session_id: str, reply_text: str) -> list[dict[str, Any]]:
    sid = str(session_id or "").strip()
    if not sid:
        return []
    try:
        rows = store.get_messages(session_id=sid, limit=120)
    except Exception:
        rows = []
    target = str(reply_text or "").strip()
    fallback: list[dict[str, Any]] = []
    matched: list[dict[str, Any]] = []
    for row in rows or []:
        role = str(getattr(row, "role", "") or "").strip().lower()
        if role != "assistant":
            continue
        atts = _parse_message_attachments(getattr(row, "attachments", None))
        if atts:
            fallback = atts
        content = str(getattr(row, "content", "") or "").strip()
        if target and content == target and atts:
            matched = atts
    return matched or fallback


def _should_suppress_channel_reply(*, channel: str, text: str) -> bool:
    ch = str(channel or "").strip().lower()
    if ch not in {"wechat", "weixin"}:
        return False
    t = str(text or "").strip()
    if not t:
        return True
    low = t.lower()
    # Silence gateway/provider credential errors for weixin user-facing channel.
    # Match variants like:
    # - Missing API key for provider "openai"
    # - Missing API key for provider 'openai'
    # - Missing API key ... provider openai
    if (
        ("missing api key" in low and "provider" in low and "openai" in low)
        or bool(re.search(r'missing\s+api\s+key.*provider\s+[\'"]?openai[\'"]?', low))
    ):
        return True
    if ("openai / 兼容 api" in t or "openai 兼容 api" in t) and "api key" in low:
        return True
    if "configure the gateway auth for that provider" in low and "openai" in low:
        return True
    return False


def process_inbound_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from runtime.operations.mcp_env import apply_gateway_mcp_env_to_os

    apply_gateway_mcp_env_to_os()
    channel_name = str(payload.get("channel") or "wecom").strip().lower()
    if channel_name in ("wecom", "wechat_work", "wxwork"):
        adapter = WeComAdapter()
        inbound = adapter.parse_inbound(payload)
    else:
        adapter = None
        inbound = _parse_generic_inbound(channel_name, payload)
    from svc.persistence.sqlite_store import SqliteStore
    from svc.config.paths import db_path

    store = SqliteStore(db_path())
    if channel_name == "wecom":
        account_id = _resolve_wecom_account_id(inbound, payload) or str(store.get_setting("wecom_bot_id") or "").strip()
    else:
        account_id = _resolve_generic_account_id(inbound, payload)
    if not account_id:
        raise ValueError(f"missing {channel_name} account_id")

    text = inbound.text.strip()
    preface = ""
    if text.lower().startswith("bind "):
        code = text.split(None, 1)[-1].strip()
        info = store.consume_bind_code(
            code=code,
            channel=inbound.channel,
            external_user_id=inbound.external_user_id,
            display_name=(
                str(inbound.metadata.get("display_name")).strip()
                if isinstance(inbound.metadata, dict) and inbound.metadata.get("display_name") is not None
                else None
            ),
        )
        reply = ("绑定成功。\n\n" + _menu_text()) if info else "绑定失败：无效或已使用的绑定码。"
    else:
        reply = ""
        reply_attachments: list[dict[str, Any]] = []
        ident = store.resolve_user_by_channel_identity_v2(
            channel=inbound.channel,
            account_id=account_id,
            external_user_id=inbound.external_user_id,
        )
        if not ident:
            owner = _ensure_administrator_owner(store)
            if owner:
                store.upsert_user_channel_account(
                    tenant_id=str(owner.get("tenant_id") or ""),
                    user_id=str(owner.get("user_id") or ""),
                    channel=inbound.channel,
                    account_id=account_id,
                    name=account_id,
                    config={"mode": "single-bot-upgraded"},
                    is_active=True,
                )
                store.upsert_channel_identity_v2(
                    tenant_id=str(owner.get("tenant_id") or ""),
                    channel=inbound.channel,
                    account_id=account_id,
                    external_user_id=inbound.external_user_id,
                    user_id=str(owner.get("user_id") or ""),
                )
                ident = store.resolve_user_by_channel_identity_v2(
                    channel=inbound.channel,
                    account_id=account_id,
                    external_user_id=inbound.external_user_id,
                )
                preface = "当前 Bot 已升级归属 administrator。"
            if not ident:
                reply = "账号初始化失败，请检查 administrator/tenant 配置。"
        if ident:
            from runtime.orchestration.policy import ActionPolicyContext, PolicyEngine
            from runtime.orchestration.security import has_explicit_confirmation_token

            tenant_id = str(ident.get("tenant_id") or "")
            user_id = str(ident.get("user_id") or "")
            role = str(ident.get("role") or "member")
            account = store.find_user_by_channel_account(channel=inbound.channel, account_id=account_id) or {}
            account_name = str(account.get("name") or "").strip() or account_id
            group_name = _extract_group_name(inbound)
            session_id = store.get_or_create_channel_session_v2(
                tenant_id=tenant_id,
                channel=inbound.channel,
                account_id=account_id,
                external_user_id=inbound.external_user_id,
                external_chat_id=inbound.external_chat_id,
                session_title=_build_channel_session_title(
                    channel=inbound.channel,
                    account_name=account_name,
                    external_user_id=inbound.external_user_id,
                    is_group=inbound.is_group,
                    group_name=group_name,
                ),
            )
            store.ensure_ui_session_owner(session_id=session_id, tenant_id=tenant_id, user_id=user_id)
            scope = "group" if inbound.is_group else "direct"
            pe = PolicyEngine()
            blob = (inbound.text or "").lower()
            mention_all = ("@all" in blob) or ("全体" in inbound.text) or ("@所有" in inbound.text)
            act = ActionPolicyContext(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                channel=inbound.channel,
                user_text=inbound.text,
                action="send_message",
                target={"is_group": bool(inbound.is_group), "mention_all": bool(mention_all)},
            )
            d = pe.decide_action(ctx=act)
            if d.needs_confirmation:
                token_key = f"confirm_token:{session_id}"
                token = (store.get_setting(token_key) or "").strip()
                if not token:
                    token = pe.new_confirmation_token()
                    store.set_setting(token_key, token)
                if not has_explicit_confirmation_token(inbound.text, token):
                    reply = f"该动作需要确认。请回复 `confirm {token}` 或包含 `[confirm:{token}]`。"
                else:
                    reply = f"[assistant] ok scope={scope} session={session_id[:8]} (confirmed)"
            else:
                if not _role_can_write(role, inbound.text):
                    reply = "你的角色暂无写入权限。请联系管理员提升权限。"
                else:
                    cmd_reply = _handle_productivity_commands(
                        text=inbound.text,
                        tenant_id=tenant_id,
                        user_id=user_id,
                    )
                    if cmd_reply is not None:
                        reply = cmd_reply
                    elif not reply:
                        user_text = (inbound.text or "").strip()
                        if user_text:
                            try:
                                from runtime.gateway import OclawGateway
                                from runtime.types import StandardMessage

                                interaction_mode, selected_specialist = _resolve_channel_dispatch(
                                    store, channel=inbound.channel, account=account
                                )
                                gw = OclawGateway(store=store)
                                msg = StandardMessage(
                                    session_id=str(session_id),
                                    tenant_id=str(tenant_id or ""),
                                    user_id=str(user_id or ""),
                                    role=str(role or "member"),
                                    channel=str(inbound.channel or "inbound"),
                                    text=str(user_text or ""),
                                    attachments=[],
                                    metadata={
                                        "tenant_id": tenant_id,
                                        "user_id": user_id,
                                        "channel": inbound.channel,
                                        "role": role,
                                        "account_id": account_id,
                                        "interaction_mode": interaction_mode,
                                        "selected_specialist": selected_specialist,
                                    },
                                )
                                manager = _build_admin_gateway_executor(
                                    store,
                                    tenant_id=tenant_id,
                                    specialist="generalist",
                                    session_id=str(session_id),
                                )
                                specialist_factory = lambda sid: _build_admin_gateway_executor(
                                    store,
                                    tenant_id=tenant_id,
                                    specialist=sid,
                                    session_id=str(session_id),
                                )
                                reply = str(
                                    gw.handle_turn(
                                        msg=msg,
                                        lang="zh",
                                        executor=manager,
                                        specialist_executor_factory=specialist_factory,
                                    ).reply_text
                                    or ""
                                ).strip()
                                reply_attachments = _collect_reply_attachments_from_history(
                                    store=store,
                                    session_id=str(session_id),
                                    reply_text=reply,
                                )
                            except Exception as e:
                                reply = f"抱歉，处理消息时出错：{type(e).__name__}: {e}"
                                reply_attachments = []
                        else:
                            reply = "收到消息，但内容为空。请直接发送文本。"
                            reply_attachments = []
        if preface:
            if reply:
                reply = f"{preface}\n\n{reply}"
            else:
                reply = f"{preface}\n\n{_menu_text()}"

    if _should_suppress_channel_reply(channel=inbound.channel, text=reply):
        return {"ok": True, "replies": []}

    if adapter is not None:
        replies = [adapter.format_outbound(OutboundMessage(external_chat_id=inbound.external_chat_id, text=reply))]
    else:
        if not reply_attachments:
            # If assistant didn't persist attachments, fall back to recent tool-produced media.
            reply_attachments = _collect_recent_tool_attachments(store=store, session_id=str(session_id))
        replies = [
            {
                "channel": inbound.channel,
                "chat_id": inbound.external_chat_id,
                "text": reply,
                "attachments": list(reply_attachments or []),
                "metadata": {},
            }
        ]
    # For wechat/weixin sidecar delivery, add a local media_path when reply attachments refer to attachment_id.
    for r in replies or []:
        if not isinstance(r, dict):
            continue
        ch = str(r.get("channel") or inbound.channel or "").strip().lower()
        if ch in {"wechat", "weixin", "whatsapp"}:
            _maybe_expand_reply_attachments_for_channel(r)
            _maybe_add_media_path_for_wechat_reply(r)
    out = {"ok": True, "replies": replies}
    return out


__all__ = ["process_inbound_payload"]

