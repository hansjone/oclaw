from __future__ import annotations

from runtime.hooks.gmail_watcher import start_gmail_watcher


def test_start_gmail_watcher_top_level_hooks_disabled() -> None:
    r = start_gmail_watcher({"hooks": {"enabled": False, "internal": {"enabled": True}}})
    assert r.started is False and r.reason == "hooks not enabled"


def test_start_gmail_watcher_internal_disabled() -> None:
    r = start_gmail_watcher({"hooks": {"internal": {"enabled": False}}})
    assert r.started is False and r.reason == "hooks not enabled"


def test_start_gmail_watcher_no_account() -> None:
    r = start_gmail_watcher({"hooks": {"internal": {"enabled": True}, "gmail": {}}})
    assert r.started is False and r.reason == "no gmail account configured"
