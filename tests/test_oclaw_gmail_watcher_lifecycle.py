from __future__ import annotations

from dataclasses import dataclass, field

from oclaw.runtime.hooks.gmail_watcher import GmailWatcherResult
from oclaw.runtime.hooks.gmail_watcher_lifecycle import start_gmail_watcher_with_logs


@dataclass
class _Log:
    infos: list[str] = field(default_factory=list)
    warns: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def info(self, msg: str) -> None:
        self.infos.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    def error(self, msg: str) -> None:
        self.errors.append(msg)


def test_gmail_lifecycle_logs_startup_success() -> None:
    log = _Log()
    start_gmail_watcher_with_logs(
        cfg={},
        log=log,
        starter=lambda _cfg: GmailWatcherResult(started=True),
    )
    assert log.infos == ["gmail watcher started"]
    assert not log.warns
    assert not log.errors


def test_gmail_lifecycle_logs_actionable_reason() -> None:
    log = _Log()
    start_gmail_watcher_with_logs(
        cfg={},
        log=log,
        starter=lambda _cfg: GmailWatcherResult(started=False, reason="auth failed"),
    )
    assert log.warns == ["gmail watcher not started: auth failed"]


def test_gmail_lifecycle_suppresses_expected_reason() -> None:
    log = _Log()
    start_gmail_watcher_with_logs(
        cfg={},
        log=log,
        starter=lambda _cfg: GmailWatcherResult(started=False, reason="hooks not enabled"),
    )
    assert not log.warns


def test_gmail_lifecycle_supports_skip_callback_oclaw_env(monkeypatch) -> None:
    monkeypatch.setenv("OCLAW_SKIP_GMAIL_WATCHER", "1")
    monkeypatch.delenv("OPENCLAW_SKIP_GMAIL_WATCHER", raising=False)
    log = _Log()
    called = {"skip": 0}
    start_gmail_watcher_with_logs(
        cfg={},
        log=log,
        on_skipped=lambda: called.__setitem__("skip", called["skip"] + 1),
        starter=lambda _cfg: GmailWatcherResult(started=True),
    )
    assert called["skip"] == 1
    assert not log.infos


def test_gmail_lifecycle_supports_skip_callback(monkeypatch) -> None:
    monkeypatch.delenv("OCLAW_SKIP_GMAIL_WATCHER", raising=False)
    monkeypatch.setenv("OPENCLAW_SKIP_GMAIL_WATCHER", "1")
    log = _Log()
    called = {"skip": 0}
    start_gmail_watcher_with_logs(
        cfg={},
        log=log,
        on_skipped=lambda: called.__setitem__("skip", called["skip"] + 1),
        starter=lambda _cfg: GmailWatcherResult(started=True),
    )
    assert called["skip"] == 1
    assert not log.infos


def test_gmail_lifecycle_logs_startup_error() -> None:
    log = _Log()

    def _raise(_cfg):
        raise RuntimeError("boom")

    start_gmail_watcher_with_logs(
        cfg={},
        log=log,
        starter=_raise,
    )
    assert log.errors == ["gmail watcher failed to start: boom"]

