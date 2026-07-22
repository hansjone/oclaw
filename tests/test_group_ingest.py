from __future__ import annotations

import pytest

from runtime.orchestration.group_ingest import (
    GROUP_SESSION_USER_SENTINEL,
    build_group_focus_instruction,
    build_group_quoted_context_block,
    build_group_sender_context,
    build_whatsapp_group_reply_metadata,
    extract_group_quoted_message,
    infer_is_group_from_chat_id,
    is_nonsend_channel_reply_text,
    normalize_jid,
    normalize_group_session_scope,
    normalize_mentioned_users_in_text,
    prepare_group_user_text_for_model,
    resolve_group_policy,
    session_user_key,
    should_inject_quoted_context,
    should_process_group_inbound,
    strip_bot_mentions_from_text,
    text_mentions_bot,
)
from interfaces.channels.base import InboundMessage
from runtime.application.gateway.inbound_service import _parse_generic_inbound, process_inbound_payload
from svc.persistence.db.engine import clear_assistant_engine_cache
from svc.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_sqlite_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.delenv("AIA_ASSISTANT_DB_BACKEND", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    dbfile = tmp_path / "group_ingest.sqlite"
    monkeypatch.setenv("AIA_ASSISTANT_DB_PATH", str(dbfile))
    clear_assistant_engine_cache()
    s = SqliteStore(str(dbfile))
    try:
        yield s
    finally:
        clear_assistant_engine_cache()


def test_normalize_jid_strips_device_suffix() -> None:
    assert normalize_jid("123456:12@s.whatsapp.net") == "123456@s.whatsapp.net"


def test_should_process_direct_messages_always() -> None:
    assert should_process_group_inbound(is_group=False, text="hi", mentions=[], bot_jid="bot@s.whatsapp.net") is True


def test_should_drop_group_without_mention_or_trigger() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="大家好",
            mentions=[],
            bot_jid="999@s.whatsapp.net",
            require_mention=True,
            triggers=["/oclaw"],
        )
        is False
    )


def test_should_accept_group_when_bot_mentioned() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="@bot hello",
            mentions=["999:0@s.whatsapp.net"],
            bot_jid="999@s.whatsapp.net",
            require_mention=True,
        )
        is True
    )


def test_should_accept_group_mention_with_lid_phone_match() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="@bot hello",
            mentions=["6281284654304@lid"],
            bot_jid="6281284654304@s.whatsapp.net",
            require_mention=True,
        )
        is True
    )


def test_should_accept_group_mention_with_bot_lid_identity() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="@bot hello",
            mentions=["176944565977182@lid"],
            bot_jid="6281284654304@s.whatsapp.net",
            require_mention=True,
            metadata={"bot_lid": "176944565977182:2@lid"},
        )
        is True
    )


def test_jids_same_user_lid_device_suffix() -> None:
    from runtime.orchestration.group_ingest import jids_same_user

    assert jids_same_user("176944565977182@lid", "176944565977182:2@lid") is True


def test_should_accept_group_when_sidecar_reports_mentions_bot_without_jids() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="@bot hi",
            mentions=[],
            bot_jid="999@s.whatsapp.net",
            require_mention=True,
            metadata={"mentions_bot": True, "raw": {"mentionsBot": True}},
        )
        is True
    )


def test_should_reject_group_when_multiple_others_mentioned_without_bot() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="@alice @bob 开会",
            mentions=[
                "111111111111@lid",
                "222222222222@lid",
            ],
            bot_jid="6281284654304@s.whatsapp.net",
            require_mention=True,
            metadata={"bot_lid": "176944565977182:2@lid"},
        )
        is False
    )


def test_should_accept_group_when_bot_among_multiple_mentions() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="@alice @bot 帮忙",
            mentions=[
                "111111111111@lid",
                "176944565977182@lid",
            ],
            bot_jid="6281284654304@s.whatsapp.net",
            require_mention=True,
            metadata={"bot_lid": "176944565977182:2@lid"},
        )
        is True
    )


def test_should_reject_group_when_only_other_user_mentioned() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="@alice hello",
            mentions=["333465375410398@lid"],
            bot_jid="6281284654304@s.whatsapp.net",
            require_mention=True,
            metadata={
                "mentions_bot": True,
                "bot_lid": "176944565977182:2@lid",
                "raw": {"mentionsBot": True, "isReplyToBot": True},
            },
        )
        is False
    )


def test_should_reject_group_when_other_mentioned_even_if_reply_to_bot() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="@alice follow up",
            mentions=["333465375410398@lid"],
            bot_jid="6281284654304@s.whatsapp.net",
            require_mention=True,
            metadata={
                "bot_lid": "176944565977182:2@lid",
                "raw": {
                    "quotedParticipant": "6281284654304@s.whatsapp.net",
                    "isReplyToBot": True,
                },
            },
        )
        is False
    )


def test_should_accept_group_reply_to_bot() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="follow up",
            mentions=[],
            bot_jid="999@s.whatsapp.net",
            require_mention=True,
            metadata={"raw": {"quotedParticipant": "999:0@s.whatsapp.net", "isReplyToBot": True}},
        )
        is True
    )


def test_text_mentions_bot_phone_fallback() -> None:
    assert text_mentions_bot(text="@1234567890 hello", bot_jid="1234567890@s.whatsapp.net") is True
    assert text_mentions_bot(text="hello", bot_jid="1234567890@s.whatsapp.net") is False


def test_should_accept_group_trigger_without_mention() -> None:
    assert (
        should_process_group_inbound(
            is_group=True,
            text="/oclaw 查天气",
            mentions=[],
            bot_jid="999@s.whatsapp.net",
            require_mention=True,
            triggers=["/oclaw"],
        )
        is True
    )


def test_enrich_quoted_ume_alarm_when_mentioned() -> None:
    from runtime.orchestration.group_ingest import (
        enrich_alert_group_question,
        extract_quoted_ume_alert_text,
    )

    meta = {"raw": {"quotedText": "[UME Alarm Raised]\nDevice: NE1", "mentionsBot": True}}
    assert extract_quoted_ume_alert_text(metadata=meta).startswith("[UME")
    enriched = enrich_alert_group_question(
        user_text="what happened?",
        quoted_alert="[UME Alarm Raised]\nDevice: NE1",
    )
    assert "[Quoted UME alarm]" in enriched
    assert "what happened?" in enriched


def test_session_user_key_group_scope() -> None:
    assert session_user_key(is_group=True, external_user_id="111@s.whatsapp.net") == "111@s.whatsapp.net"
    assert session_user_key(is_group=True, external_user_id="111@s.whatsapp.net", session_scope="chat") == GROUP_SESSION_USER_SENTINEL
    assert session_user_key(is_group=False, external_user_id="111@s.whatsapp.net") == "111@s.whatsapp.net"


def test_normalize_group_session_scope() -> None:
    assert normalize_group_session_scope("chat") == "chat"
    assert normalize_group_session_scope("shared") == "chat"
    assert normalize_group_session_scope("user_in_chat") == "user_in_chat"
    assert normalize_group_session_scope("") == "user_in_chat"


def test_resolve_group_policy_from_account_config() -> None:
    policy = resolve_group_policy(
        account={
            "config": {
                "group_policy": {
                    "require_mention": False,
                    "triggers": ["!ask"],
                    "session_scope": "chat",
                }
            }
        }
    )
    assert policy.require_mention is False
    assert policy.triggers == ("!ask",)
    assert policy.session_scope == "chat"


def test_infer_is_group_from_chat_id() -> None:
    assert infer_is_group_from_chat_id("120363012345678@g.us") is True
    assert infer_is_group_from_chat_id("111@s.whatsapp.net") is False


def test_parse_generic_inbound_infers_whatsapp_group() -> None:
    inbound = _parse_generic_inbound(
        "whatsapp",
        {
            "user_id": "111@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "hello",
        },
    )
    assert inbound.is_group is True


def test_is_nonsend_channel_reply_text() -> None:
    assert is_nonsend_channel_reply_text("") is True
    assert is_nonsend_channel_reply_text("(silent)") is True
    assert is_nonsend_channel_reply_text("（silent）") is True
    assert is_nonsend_channel_reply_text("NO_REPLY") is True
    assert is_nonsend_channel_reply_text("你好") is False


def test_inbound_group_without_is_group_flag_is_still_silent(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    _setup_whatsapp_identity(store)
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    out = process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "111@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "Test alarm",
            "metadata": {"bot_jid": "999@s.whatsapp.net", "source": "test"},
        }
    )
    assert out.get("replies") == []


def test_inbound_suppresses_silent_llm_reply(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    _setup_whatsapp_identity(store)
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    class _Turn:
        turn_uuid = "turn-s"
        reply_text = "(silent)"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            _ = store

        def handle_turn(self, **kwargs: object) -> _Turn:
            return _Turn()

    monkeypatch.setattr("runtime.gateway.OclawGateway", _Gw)

    out = process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "111@s.whatsapp.net",
            "chat_id": "111@s.whatsapp.net",
            "text": "ping",
            "is_group": False,
            "metadata": {"bot_jid": "999@s.whatsapp.net"},
        }
    )
    assert out.get("replies") == []


def test_build_group_sender_context() -> None:
    ctx = build_group_sender_context(
        metadata={"raw": {"pushName": "Alice"}},
        external_user_id="111@s.whatsapp.net",
    )
    assert ctx == "[发言: Alice]"
    assert "111@s.whatsapp.net" not in ctx


def test_strip_bot_mentions_from_text() -> None:
    meta = {"bot_lid": "162788605444170@lid", "bot_push_name": "oliver"}
    out = strip_bot_mentions_from_text(
        text="@162788605444170 生成小鹿照片",
        bot_jid="8618142387786@s.whatsapp.net",
        metadata=meta,
    )
    assert out == "生成小鹿照片"


def test_normalize_mentioned_users_in_text_uses_nickname() -> None:
    out = normalize_mentioned_users_in_text(
        text="每三分钟提醒@200846277140511 喝水",
        mention_jids=["200846277140511@lid"],
        mention_names=["吴华"],
    )
    assert out == "每三分钟提醒@吴华 喝水"


def test_prepare_group_user_text_for_model_user_in_chat() -> None:
    out = prepare_group_user_text_for_model(
        text="@162788605444170 每三分钟提醒@200846277140511 喝水",
        metadata={"bot_lid": "162788605444170@lid", "bot_push_name": "oliver"},
        mentions=["162788605444170@lid", "200846277140511@lid"],
        bot_jid="8618142387786@s.whatsapp.net",
        session_scope="user_in_chat",
        external_user_id="8618142387786@s.whatsapp.net",
        filtered_mention_jids=["200846277140511@lid"],
        mention_names=["吴华"],
    )
    assert out == "每三分钟提醒@吴华 喝水"
    assert "[发言:" not in out


def test_prepare_group_user_text_for_model_shared_chat_prefix() -> None:
    out = prepare_group_user_text_for_model(
        text="@999 帮忙",
        metadata={"raw": {"pushName": "Alice"}},
        mentions=["999@s.whatsapp.net"],
        bot_jid="999@s.whatsapp.net",
        session_scope="chat",
        external_user_id="111@s.whatsapp.net",
    )
    assert out.startswith("[发言: Alice]")
    assert out.endswith("帮忙")
    assert "@999" not in out


def test_build_group_focus_instruction() -> None:
    zh = build_group_focus_instruction()
    en = build_group_focus_instruction(lang="en")
    assert "群聊规则" in zh
    assert "current sender" in en


def test_extract_group_quoted_message_and_build_context_block() -> None:
    meta = {
        "raw": {
            "quotedText": "服务器刚刚 502 了",
            "quotedParticipant": "111@s.whatsapp.net",
            "quotedPushName": "Alice",
            "quotedStanzaId": "Q1",
        }
    }
    info = extract_group_quoted_message(metadata=meta)
    assert info["quoted_text"] == "服务器刚刚 502 了"
    assert info["quoted_push_name"] == "Alice"
    block = build_group_quoted_context_block(metadata=meta)
    assert "[被引用消息]" in block
    assert "Alice" in block


def test_should_inject_quoted_context_dedupes_recent_message() -> None:
    from svc.persistence.sqlite_store import ChatMessage

    recent = [
        ChatMessage(
            id=1,
            session_id="s1",
            role="assistant",
            content="server just returned HTTP 502",
            tool_calls=None,
            timestamp="",
        )
    ]
    assert should_inject_quoted_context(quoted_text="server just returned HTTP 502", recent_messages=recent) is False
    assert should_inject_quoted_context(quoted_text="a totally different question", recent_messages=recent) is True


def test_should_inject_quoted_context_strips_whatsapp_mention_prefix() -> None:
    from svc.persistence.sqlite_store import ChatMessage

    body = (
        "### KND-SMNR-EN1-Z20HS — LLDP Neighbors\n\n"
        "| Device | Port | Peer Device |\n"
        "|---|---|---|\n"
        "| KND-SMNR-EN1-Z20HS | cgei-1/1/0/33 | KND-LGGO-EN1-Z20HS |\n"
        "KND-SMNR-EN1 has only 2 LLDP neighbors in the Kendahe area.\n"
    )
    recent = [
        ChatMessage(
            id=10,
            session_id="s1",
            role="assistant",
            content=body,
            tool_calls=None,
            timestamp="",
            event_type="assistant_text",
        )
    ]
    # WhatsApp reply-to often prefixes the bot body with @<bot lid/jid>.
    quoted = f"@68458037407987 {body}"
    assert should_inject_quoted_context(quoted_text=quoted, recent_messages=recent) is False


def test_should_inject_quoted_context_finds_assistant_buried_under_tools() -> None:
    from svc.persistence.sqlite_store import ChatMessage

    body = (
        "KND-SMNR-EN1 has only 2 LLDP neighbors — both access-layer devices "
        "in the Kendahe area connected via cgei ports."
    )
    rows = [
        ChatMessage(
            id=1,
            session_id="s1",
            role="assistant",
            content=body,
            tool_calls=None,
            timestamp="",
            event_type="assistant_text",
        )
    ]
    for i in range(2, 20):
        rows.append(
            ChatMessage(
                id=i,
                session_id="s1",
                role="tool",
                content=f'{{"ok": true, "n": {i}}}',
                tool_calls=None,
                timestamp="",
                event_type="tool_result",
            )
        )
    assert should_inject_quoted_context(quoted_text=f"@bot {body}", recent_messages=rows) is False
    assert should_inject_quoted_context(quoted_text="totally new topic xyz about fans", recent_messages=rows) is True


def test_build_whatsapp_group_reply_metadata() -> None:
    inbound = InboundMessage(
        channel="whatsapp",
        external_user_id="111:12@s.whatsapp.net",
        external_chat_id="120363012345678@g.us",
        text="明天几点？",
        is_group=True,
        metadata={
            "raw": {
                "id": "MSG123",
                "participant": "111:12@s.whatsapp.net",
                "pushName": "Alice",
            }
        },
    )
    meta = build_whatsapp_group_reply_metadata(inbound=inbound)
    assert meta["quote_stanza_id"] == "MSG123"
    assert meta["mention_jids"] == ["111:12@s.whatsapp.net"]
    assert meta["quote_text"] == "明天几点？"
    assert meta["quote_participant"] == "111:12@s.whatsapp.net"
    assert meta["mention_names"] == ["Alice"]


def test_default_group_session_is_per_user(fresh_sqlite_store: SqliteStore) -> None:
    store = fresh_sqlite_store
    tenant = store.create_tenant("WA")
    chat_id = "120363012345678@g.us"
    sid_a = store.get_or_create_channel_session_v2(
        tenant_id=str(tenant["id"]),
        channel="whatsapp",
        account_id="wa-default",
        external_chat_id=chat_id,
        external_user_id=session_user_key(is_group=True, external_user_id="111@s.whatsapp.net"),
        session_title="whatsapp|test+Family",
    )
    sid_b = store.get_or_create_channel_session_v2(
        tenant_id=str(tenant["id"]),
        channel="whatsapp",
        account_id="wa-default",
        external_chat_id=chat_id,
        external_user_id=session_user_key(is_group=True, external_user_id="222@s.whatsapp.net"),
        session_title="whatsapp|test+Family",
    )
    assert sid_a != sid_b


def test_shared_group_session_for_multiple_senders_when_scope_chat(fresh_sqlite_store: SqliteStore) -> None:
    store = fresh_sqlite_store
    tenant = store.create_tenant("WA")
    chat_id = "120363012345678@g.us"
    sid_a = store.get_or_create_channel_session_v2(
        tenant_id=str(tenant["id"]),
        channel="whatsapp",
        account_id="wa-default",
        external_chat_id=chat_id,
        external_user_id=session_user_key(
            is_group=True,
            external_user_id="111@s.whatsapp.net",
            session_scope="chat",
        ),
        session_title="whatsapp|test+Family",
    )
    sid_b = store.get_or_create_channel_session_v2(
        tenant_id=str(tenant["id"]),
        channel="whatsapp",
        account_id="wa-default",
        external_chat_id=chat_id,
        external_user_id=session_user_key(
            is_group=True,
            external_user_id="222@s.whatsapp.net",
            session_scope="chat",
        ),
        session_title="whatsapp|test+Family",
    )
    assert sid_a == sid_b


def _setup_whatsapp_identity(store: SqliteStore, *, extra_user_ids: list[str] | None = None) -> tuple[str, str]:
    tenant = store.create_tenant("WA")
    tenant_id = str(tenant["id"])
    user = store.create_user(tenant_id=tenant_id, display_name="Admin", role="owner")
    user_id = str(user["id"])
    store.upsert_user_channel_account(
        tenant_id=tenant_id,
        user_id=user_id,
        channel="whatsapp",
        account_id="wa-default",
        name="wa-default",
        config={"group_policy": {"require_mention": True, "triggers": ["/oclaw"]}},
        is_active=True,
    )
    for ext_uid in ["111@s.whatsapp.net", *(extra_user_ids or [])]:
        store.upsert_channel_identity_v2(
            tenant_id=tenant_id,
            channel="whatsapp",
            account_id="wa-default",
            external_user_id=ext_uid,
            user_id=user_id,
        )
        store.upsert_whatsapp_contact(
            tenant_id=tenant_id,
            account_id="wa-default",
            external_user_id=ext_uid,
            phone="".join(ch for ch in ext_uid.split("@", 1)[0] if ch.isdigit()),
            list_type="whitelist",
        )
    return tenant_id, user_id


def test_inbound_group_without_mention_is_silent(monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore) -> None:
    store = fresh_sqlite_store
    _setup_whatsapp_identity(store)
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    out = process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "111@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "大家晚上好",
            "is_group": True,
            "mentions": [],
            "metadata": {"bot_jid": "999@s.whatsapp.net", "source": "test"},
        }
    )
    assert out.get("ok") is True
    assert out.get("replies") == []


def test_inbound_dm_still_processes_without_mention(monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore) -> None:
    store = fresh_sqlite_store
    _setup_whatsapp_identity(store)
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)
    # Keep sync replies so this unit test can assert HTTP response shape.
    monkeypatch.setenv("OCLAW_WHATSAPP_INBOUND_QUEUE_DELIVERY", "0")

    captured: dict[str, str] = {}

    class _Turn:
        turn_uuid = "turn-1"
        reply_text = "pong"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            _ = store

        def handle_turn(self, **kwargs: object) -> _Turn:
            msg = kwargs.get("msg")
            captured["text"] = str(getattr(msg, "text", "") or "")
            return _Turn()

    monkeypatch.setattr("runtime.gateway.OclawGateway", _Gw)

    out = process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "111@s.whatsapp.net",
            "chat_id": "111@s.whatsapp.net",
            "text": "ping",
            "is_group": False,
            "mentions": [],
            "metadata": {"bot_jid": "999@s.whatsapp.net"},
        }
    )
    replies = out.get("replies") if isinstance(out.get("replies"), list) else []
    assert replies and str(replies[0].get("text") or "") == "pong"
    assert "[群成员:" not in captured.get("text", "")


def test_inbound_group_mention_uses_per_user_session_and_sender_prefix(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    tenant_id, user_id = _setup_whatsapp_identity(store, extra_user_ids=["222@s.whatsapp.net"])
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    captured: dict[str, str] = {}
    session_ids: list[str] = []

    class _Turn:
        turn_uuid = "turn-g"
        reply_text = "group-ok"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            _ = store

        def handle_turn(self, **kwargs: object) -> _Turn:
            msg = kwargs.get("msg")
            captured["text"] = str(getattr(msg, "text", "") or "")
            session_ids.append(str(getattr(msg, "session_id", "") or ""))
            return _Turn()

    monkeypatch.setattr("runtime.gateway.OclawGateway", _Gw)

    chat_id = "120363012345678@g.us"
    base = {
        "channel": "whatsapp",
        "account_id": "wa-default",
        "chat_id": chat_id,
        "is_group": True,
        "metadata": {"bot_jid": "999@s.whatsapp.net", "source": "test"},
    }

    process_inbound_payload(
        {
            **base,
            "user_id": "111@s.whatsapp.net",
            "text": "@999 hi",
            "mentions": ["999@s.whatsapp.net"],
            "metadata": {**base["metadata"], "raw": {"pushName": "Alice"}},
        }
    )
    process_inbound_payload(
        {
            **base,
            "user_id": "222@s.whatsapp.net",
            "text": "@999 again",
            "mentions": ["999@s.whatsapp.net"],
            "metadata": {**base["metadata"], "raw": {"pushName": "Bob"}},
        }
    )

    assert len(session_ids) == 2
    assert session_ids[0] != session_ids[1]
    assert "[群成员:" not in captured["text"]
    assert "[发言:" not in captured["text"]
    assert captured["text"] == "again"
    assert "群聊规则" not in captured["text"]

    sid = store.get_or_create_channel_session_v2(
        tenant_id=tenant_id,
        channel="whatsapp",
        account_id="wa-default",
        external_chat_id=chat_id,
        external_user_id="111@s.whatsapp.net",
        session_title="whatsapp|wa-default+Family",
    )
    assert sid == session_ids[0]

    _ = tenant_id, user_id


def test_inbound_group_scope_chat_uses_shared_session(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    tenant_id, user_id = _setup_whatsapp_identity(store, extra_user_ids=["222@s.whatsapp.net"])
    store.upsert_user_channel_account(
        tenant_id=tenant_id,
        user_id=user_id,
        channel="whatsapp",
        account_id="wa-default",
        name="wa-default",
        config={
            "group_policy": {
                "require_mention": True,
                "triggers": ["/oclaw"],
                "session_scope": "chat",
            }
        },
        is_active=True,
    )
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    session_ids: list[str] = []

    class _Turn:
        turn_uuid = "turn-g"
        reply_text = "group-ok"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            _ = store

        def handle_turn(self, **kwargs: object) -> _Turn:
            msg = kwargs.get("msg")
            session_ids.append(str(getattr(msg, "session_id", "") or ""))
            return _Turn()

    monkeypatch.setattr("runtime.gateway.OclawGateway", _Gw)

    chat_id = "120363012345678@g.us"
    base = {
        "channel": "whatsapp",
        "account_id": "wa-default",
        "chat_id": chat_id,
        "is_group": True,
        "metadata": {"bot_jid": "999@s.whatsapp.net", "source": "test"},
    }
    process_inbound_payload(
        {
            **base,
            "user_id": "111@s.whatsapp.net",
            "text": "@bot hi",
            "mentions": ["999@s.whatsapp.net"],
            "metadata": {**base["metadata"], "raw": {"pushName": "Alice"}},
        }
    )
    process_inbound_payload(
        {
            **base,
            "user_id": "222@s.whatsapp.net",
            "text": "@bot again",
            "mentions": ["999@s.whatsapp.net"],
            "metadata": {**base["metadata"], "raw": {"pushName": "Bob"}},
        }
    )
    assert len(session_ids) == 2
    assert session_ids[0] == session_ids[1]

    sid = store.get_or_create_channel_session_v2(
        tenant_id=tenant_id,
        channel="whatsapp",
        account_id="wa-default",
        external_chat_id=chat_id,
        external_user_id=GROUP_SESSION_USER_SENTINEL,
        session_title="whatsapp|wa-default+Family",
    )
    assert sid == session_ids[0]
    _ = user_id


def test_inbound_group_injects_quoted_context_when_not_in_current_session(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    tenant_id, user_id = _setup_whatsapp_identity(store, extra_user_ids=["222@s.whatsapp.net"])
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    captured: dict[str, str] = {}

    class _Turn:
        turn_uuid = "turn-q"
        reply_text = "ok"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            _ = store

        def handle_turn(self, **kwargs: object) -> _Turn:
            msg = kwargs.get("msg")
            captured["text"] = str(getattr(msg, "text", "") or "")
            return _Turn()

    monkeypatch.setattr("runtime.gateway.OclawGateway", _Gw)

    out = process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "222@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "@bot 这是不是和刚才发布有关？",
            "is_group": True,
            "mentions": ["999@s.whatsapp.net"],
            "metadata": {
                "bot_jid": "999@s.whatsapp.net",
                "raw": {
                    "pushName": "Bob",
                    "quotedText": "看起来像 OSPF 邻居抖动",
                    "quotedParticipant": "999@s.whatsapp.net",
                    "quotedPushName": "oclaw",
                    "quotedStanzaId": "Q2",
                },
            },
        }
    )
    assert out.get("ok") is True
    assert "[被引用消息]" in captured["text"]
    assert "看起来像 OSPF 邻居抖动" in captured["text"]
    _ = tenant_id, user_id


def test_inbound_group_skips_quoted_context_when_already_in_current_session(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    tenant_id, user_id = _setup_whatsapp_identity(store)
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    call_no = {"n": 0}
    captured: dict[str, str] = {}
    prior_reply = "Looks like OSPF neighbor flapping"

    class _Turn:
        turn_uuid = "turn-q2"

        @property
        def reply_text(self) -> str:
            return prior_reply if call_no["n"] == 1 else "continue analysis"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            self._store = store

        def handle_turn(self, **kwargs: object) -> _Turn:
            call_no["n"] += 1
            msg = kwargs.get("msg")
            captured["text"] = str(getattr(msg, "text", "") or "")
            turn = _Turn()
            # Real gateway persists assistant text; mock must do the same so quote
            # dedupe can see the prior reply in session history.
            sid = str(getattr(msg, "session_id", "") or "").strip()
            if sid and turn.reply_text:
                self._store.add_message(
                    sid,
                    "assistant",
                    turn.reply_text,
                    event_type="assistant_text",
                )
            return turn

    monkeypatch.setattr("runtime.gateway.OclawGateway", _Gw)

    process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "111@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "@bot please diagnose first",
            "is_group": True,
            "mentions": ["999@s.whatsapp.net"],
            "metadata": {"bot_jid": "999@s.whatsapp.net", "raw": {"pushName": "Alice"}},
        }
    )
    out = process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "111@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "@bot what is the next check?",
            "is_group": True,
            "mentions": ["999@s.whatsapp.net"],
            "metadata": {
                "bot_jid": "999@s.whatsapp.net",
                "raw": {
                    "pushName": "Alice",
                    # WhatsApp reply-to often prefixes the bot body with @<bot jid/lid>.
                    "quotedText": f"@999 {prior_reply}",
                    "quotedParticipant": "999@s.whatsapp.net",
                    "quotedPushName": "oclaw",
                    "quotedStanzaId": "Q3",
                },
            },
        }
    )
    assert out.get("ok") is True
    assert "[被引用消息]" not in captured["text"]
    _ = tenant_id, user_id


def test_inbound_group_reply_includes_quote_and_mention_metadata(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    _setup_whatsapp_identity(store)
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)
    monkeypatch.setenv("OCLAW_WHATSAPP_INBOUND_QUEUE_DELIVERY", "0")

    class _Turn:
        turn_uuid = "turn-g"
        reply_text = "afternoon three"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            _ = store

        def handle_turn(self, **kwargs: object) -> _Turn:
            return _Turn()

    monkeypatch.setattr("runtime.gateway.OclawGateway", _Gw)

    out = process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "111@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "@bot tomorrow when?",
            "is_group": True,
            "mentions": ["999@s.whatsapp.net"],
            "metadata": {
                "bot_jid": "999@s.whatsapp.net",
                "raw": {"id": "ABC123", "participant": "111@s.whatsapp.net", "pushName": "Alice"},
            },
        }
    )
    replies = out.get("replies") if isinstance(out.get("replies"), list) else []
    assert replies
    meta = replies[0].get("metadata") if isinstance(replies[0], dict) else {}
    assert isinstance(meta, dict)
    assert meta.get("quote_stanza_id") == "ABC123"
    assert meta.get("mention_jids") == ["111@s.whatsapp.net"]
    assert meta.get("quote_text") == "@bot tomorrow when?"


def test_inbound_group_schedule_mention_metadata_preserved_after_text_clean(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    tenant_id, _ = _setup_whatsapp_identity(store)
    store.upsert_whatsapp_contact(
        tenant_id=tenant_id,
        account_id="wa-default",
        external_user_id="200846277140511@lid",
        push_name="WuHua",
        list_type="whitelist",
    )
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    captured: dict[str, object] = {}

    class _Turn:
        turn_uuid = "turn-sched"
        reply_text = "ok"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            _ = store

        def handle_turn(self, **kwargs: object) -> _Turn:
            msg = kwargs.get("msg")
            captured["text"] = str(getattr(msg, "text", "") or "")
            captured["metadata"] = getattr(msg, "metadata", None)
            return _Turn()

    monkeypatch.setattr("runtime.gateway.OclawGateway", _Gw)

    process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "111@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "@999 remind @200846277140511 water",
            "is_group": True,
            "mentions": ["999@s.whatsapp.net", "200846277140511@lid"],
            "metadata": {
                "bot_jid": "999@s.whatsapp.net",
                "bot_lid": "162788605444170@lid",
                "raw": {"pushName": "Alice"},
            },
        }
    )

    meta = captured.get("metadata") if isinstance(captured.get("metadata"), dict) else {}
    assert "200846277140511@lid" in list(meta.get("mentioned_jids") or [])
    assert meta.get("raw_inbound_text")
    text = str(captured.get("text") or "")
    assert "200846277140511" not in text
    assert "@WuHua" in text
    assert "@999" not in text


def test_channel_group_session_visible_in_administrator_chat_list(
    monkeypatch: pytest.MonkeyPatch, fresh_sqlite_store: SqliteStore
) -> None:
    store = fresh_sqlite_store
    tenant_id, owner_user_id = _setup_whatsapp_identity(store, extra_user_ids=["222@s.whatsapp.net"])
    monkeypatch.setattr("svc.persistence.assistant_store.get_assistant_store", lambda: store)

    session_ids: list[str] = []

    class _Turn:
        turn_uuid = "turn-guest"
        reply_text = "ok"

    class _Gw:
        def __init__(self, *, store: object) -> None:
            _ = store

        def handle_turn(self, **kwargs: object) -> _Turn:
            msg = kwargs.get("msg")
            session_ids.append(str(getattr(msg, "session_id", "") or ""))
            return _Turn()

    monkeypatch.setattr("runtime.gateway.OclawGateway", _Gw)

    process_inbound_payload(
        {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "222@s.whatsapp.net",
            "chat_id": "120363012345678@g.us",
            "text": "@999 hello from bob",
            "is_group": True,
            "mentions": ["999@s.whatsapp.net"],
            "metadata": {"bot_jid": "999@s.whatsapp.net", "raw": {"pushName": "Bob"}},
        }
    )

    assert session_ids
    owner = store.get_ui_session_owner(session_id=session_ids[0]) or {}
    assert owner.get("user_id") == owner_user_id

    listed = store.list_sessions_for_administrator_chat_view(
        username="administrator",
        tenant_id=tenant_id,
        limit=20,
        offset=0,
    )
    listed_ids = {s.id for s in listed}
    assert session_ids[0] in listed_ids
