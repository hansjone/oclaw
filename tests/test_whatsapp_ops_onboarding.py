from __future__ import annotations

from runtime.application.gateway.inbound_service import _handle_productivity_commands, _menu_text
from runtime.extensions.whatsapp.access_control import (
    access_granted_guide_text,
    whatsapp_ops_help_text,
)


def test_whatsapp_ops_help_is_english_field_guide() -> None:
    text = whatsapp_ops_help_text(lang="en")
    assert "fiber" in text.lower() or "alarm" in text.lower()
    assert "@mention" in text.lower() or "mention" in text.lower()
    assert "记待办" not in text


def test_access_granted_guide_includes_ops_help() -> None:
    text = access_granted_guide_text(lang="en")
    assert "Access approved" in text
    assert "YES" in text or "continue" in text.lower()


def test_menu_text_whatsapp_not_productivity_chinese() -> None:
    text = _menu_text(channel="whatsapp")
    assert "记待办" not in text
    assert "fiber" in text.lower() or "alarm" in text.lower()
    assert "记待办" in _menu_text(channel="weixin")


def test_productivity_help_on_whatsapp_returns_ops_guide() -> None:
    out = _handle_productivity_commands(
        text="help",
        tenant_id="t1",
        user_id="u1",
        channel="whatsapp",
    )
    assert out is not None
    assert "记待办" not in out
    assert "fiber" in out.lower() or "offline" in out.lower() or "alarm" in out.lower()
