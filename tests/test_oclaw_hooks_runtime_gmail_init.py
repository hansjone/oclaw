from __future__ import annotations

from pathlib import Path

from oclaw.runtime.hooks_runtime import _reset_hooks_runtime_state_for_test, initialize_hooks_runtime


def test_initialize_hooks_runtime_invokes_gmail_lifecycle(monkeypatch, tmp_path: Path) -> None:
    _reset_hooks_runtime_state_for_test()
    calls: list[object] = []

    def _cap(*, cfg, log, on_skipped=None, starter=None):
        calls.append(cfg)

    monkeypatch.setattr(
        "oclaw.runtime.hooks.gmail_watcher_lifecycle.start_gmail_watcher_with_logs",
        _cap,
    )
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    monkeypatch.setattr("oclaw.runtime.hooks_runtime.runtime_hooks_bundled_root", lambda: str(bundled))
    monkeypatch.setattr("oclaw.runtime.hooks.merge_skill_hook_dirs.discover_workspace_skill_manifests", lambda: ())

    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = {"hooks": {"internal": {"enabled": True}}}
    initialize_hooks_runtime(cfg=cfg, workspace_dir=str(ws))
    assert len(calls) == 1
    assert isinstance(calls[0], dict)
