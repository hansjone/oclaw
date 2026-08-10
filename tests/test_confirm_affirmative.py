from __future__ import annotations

from runtime.orchestration.security import has_explicit_confirmation_token


def test_whatsapp_yes_confirms_outstanding_token() -> None:
    assert has_explicit_confirmation_token("@bot YES", "abc123")
    assert has_explicit_confirmation_token("YES", "abc123")
    assert has_explicit_confirmation_token("please continue", "abc123")
    assert has_explicit_confirmation_token("确认", "abc123")
    assert not has_explicit_confirmation_token("YES", None)
    assert not has_explicit_confirmation_token("maybe later", "abc123")
    assert has_explicit_confirmation_token("confirm abc123", "abc123")
