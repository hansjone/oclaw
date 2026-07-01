from __future__ import annotations

from runtime.extensions.whatsapp.access_control import (
    admin_notify_text,
    extract_quote_context,
    is_access_allowed,
    normalize_whatsapp_phone,
    parse_admin_access_command,
    parse_admin_approval_intent,
    parse_pending_id_from_notify_text,
    resolve_sender_phone,
    resolve_whatsapp_sender_jid,
    whatsapp_phones_match,
    whatsapp_users_match,
)


def test_blacklist_mode_denies_by_default() -> None:
    assert is_access_allowed(access_mode="blacklist", list_type=None) is False
    assert is_access_allowed(access_mode="blacklist", list_type="whitelist") is True
    assert is_access_allowed(access_mode="blacklist", list_type="blacklist") is False
    assert is_access_allowed(access_mode="blacklist", list_type="admin") is True


def test_whitelist_mode_allows_by_default() -> None:
    assert is_access_allowed(access_mode="whitelist", list_type=None) is True
    assert is_access_allowed(access_mode="whitelist", list_type="blacklist") is False
    assert is_access_allowed(access_mode="whitelist", list_type="whitelist") is True


def test_admin_approval_intent() -> None:
    assert parse_admin_approval_intent("yes") == "approve"
    assert parse_admin_approval_intent("NO") == "deny"
    assert parse_admin_approval_intent("add to whitelist") == "approve"
    assert parse_admin_approval_intent("hello") is None


def test_whatsapp_users_match_lid_alias() -> None:
    assert whatsapp_users_match("91010910658657@lid", "91010910658657@s.whatsapp.net") is True


def test_resolve_whatsapp_sender_jid_uses_participant_alt() -> None:
    jid = resolve_whatsapp_sender_jid(
        "91010910658657@lid",
        {"raw": {"participantAlt": "8618142387786@s.whatsapp.net"}},
    )
    assert jid == "8618142387786@s.whatsapp.net"


def test_normalize_whatsapp_phone() -> None:
    assert normalize_whatsapp_phone("+8615601877957") == "8615601877957"
    assert normalize_whatsapp_phone("8615601877957@s.whatsapp.net") == "8615601877957"


def test_resolve_sender_phone_prefers_participant_alt() -> None:
    phone = resolve_sender_phone(
        "91010910658657@lid",
        "8618142387786@s.whatsapp.net",
    )
    assert phone == "8618142387786"


def test_resolve_sender_phone_uses_remote_jid_alt_for_dm() -> None:
    phone = resolve_sender_phone(
        "91010910658657@lid",
        "",
        "8615601877957@s.whatsapp.net",
    )
    assert phone == "8615601877957"


def test_phone_from_jid_ignores_lid() -> None:
    from runtime.extensions.whatsapp.access_control import phone_from_jid

    assert phone_from_jid("91010910658657@lid") == ""


def test_resolve_whatsapp_sender_jid_uses_remote_jid_alt() -> None:
    jid = resolve_whatsapp_sender_jid(
        "91010910658657@lid",
        {"raw": {"remoteJidAlt": "8615601877957@s.whatsapp.net"}},
    )
    assert jid == "8615601877957@s.whatsapp.net"


def test_whatsapp_phones_match_across_formats() -> None:
    assert whatsapp_phones_match("+8615601877957", "8615601877957@s.whatsapp.net") is True


def test_coerce_whatsapp_access_target_normalizes_phone() -> None:
    from runtime.extensions.whatsapp.access_control import coerce_whatsapp_access_target

    assert coerce_whatsapp_access_target("+8618142387786") == "8618142387786@s.whatsapp.net"
    assert coerce_whatsapp_access_target("8615601877957") == "8615601877957@s.whatsapp.net"


def test_admin_access_commands() -> None:
    cmd = parse_admin_access_command("whitelist add +8615601877957")
    assert cmd and cmd.get("action") == "set_list" and cmd.get("list_type") == "whitelist"
    mode = parse_admin_access_command("access mode blacklist")
    assert mode and mode.get("access_mode") == "blacklist"


def test_parse_pending_id_from_notify_text() -> None:
    zh = "[oclaw] 未授权用户请求访问\n请求编号: abcdef0123456789\n"
    en = "[oclaw] Unauthorized access request\nRequest: fedcba9876543210\n"
    assert parse_pending_id_from_notify_text(zh) == "abcdef0123456789"
    assert parse_pending_id_from_notify_text(en) == "fedcba9876543210"
    assert parse_pending_id_from_notify_text("no id here") is None


def test_extract_quote_context() -> None:
    ctx = extract_quote_context(
        {
            "raw": {
                "quotedStanzaId": "stanza_notify_1",
                "quotedText": "Request: abc123",
                "participant": "111@s.whatsapp.net",
                "remoteJid": "222@s.whatsapp.net",
            }
        }
    )
    assert ctx["stanza_id"] == "stanza_notify_1"
    assert ctx["quoted_text"] == "Request: abc123"
    assert ctx["participant"] == "111@s.whatsapp.net"
    assert ctx["remote_jid"] == "222@s.whatsapp.net"


def test_admin_notify_text_prompts_quote_reply() -> None:
    zh = admin_notify_text(
        lang="zh",
        push_name="Bob",
        external_user_id="8615601877957@s.whatsapp.net",
        request_text="hi",
        pending_id="pending123",
    )
    en = admin_notify_text(
        lang="en",
        push_name="Bob",
        external_user_id="8615601877957@s.whatsapp.net",
        request_text="hi",
        pending_id="pending123",
    )
    assert "请引用本条消息" in zh
    assert "quoting this message" in en
