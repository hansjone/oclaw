from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_weixin_start_defaults_to_official_runner() -> None:
    text = _read("runtime/operations/scripts/weixin_start.ps1")
    assert '$runnerMode = "official"' in text
    assert '$runnerFile = "official_runner.ts"' in text
    assert 'AIA_WEIXIN_RUNNER_MODE' in text
    assert 'official_runner.ts' in text


def test_weixin_status_and_stop_track_official_runner() -> None:
    status_text = _read("runtime/operations/scripts/weixin_status.ps1")
    stop_text = _read("runtime/operations/scripts/weixin_stop.ps1")
    assert "official_runner.ts" in status_text
    assert "official_runner.ts" in stop_text


def test_weixin_install_copies_official_runner() -> None:
    text = _read("runtime/operations/scripts/weixin_install.ps1")
    assert 'Copy-Item -Path (Join-Path $bridgeSrc "official_runner.ts")' in text
    assert "Ensure-OfficialPluginRuntimeDeps" in text


def test_weixin_start_ensures_plugin_runtime_deps() -> None:
    text = _read("runtime/operations/scripts/weixin_start.ps1")
    assert "Ensure-OfficialPluginRuntimeDeps" in text
    assert "npm.cmd install openclaw@latest --no-save" in text


def test_official_runner_prefers_direct_inbound_before_other_fallbacks() -> None:
    text = _read("runtime/operations/weixin_bridge/official_runner.ts")
    assert "const native = await postNativeReply" in text
    assert "falling back to direct /inbound bridge" not in text
    assert "legacy local ilink bridge" not in text


def test_official_runner_logs_active_bridge_path() -> None:
    text = _read("runtime/operations/weixin_bridge/official_runner.ts")
    assert "official runner started account=" in text
    assert "native reply failed; no fallback enabled" in text
