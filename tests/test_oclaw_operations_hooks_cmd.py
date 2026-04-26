from __future__ import annotations

import argparse
import json
from io import StringIO
import sys

def test_build_hooks_status_report_empty_workspace(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from oclaw.runtime.operations.hooks_cmd import build_hooks_status_report

    r = build_hooks_status_report(str(tmp_path), config={"hooks": {"internal": {"enabled": True}}})
    assert "summary" in r and "hooks" in r
    assert r["workspace_dir"] == str(tmp_path)


def test_hooks_list_json(capsys, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from oclaw.runtime.operations.hooks_cmd import _cmd_hooks_list

    ns = argparse.Namespace(workspace=str(tmp_path), json=True, eligible=False, verbose=False)
    assert _cmd_hooks_list(ns) == 0
    out = capsys.readouterr().out
    obj = json.loads(out)
    assert obj["workspace_dir"] == str(tmp_path)
    assert "hooks" in obj


def test_hooks_check_text(capsys, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from oclaw.runtime.operations.hooks_cmd import _cmd_hooks_check

    ns = argparse.Namespace(workspace=str(tmp_path), json=False)
    assert _cmd_hooks_check(ns) == 0
    assert "Hooks status" in capsys.readouterr().out


def test_hooks_info_missing(capsys, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from oclaw.runtime.operations.hooks_cmd import _cmd_hooks_info

    ns = argparse.Namespace(workspace=str(tmp_path), name="nonexistent-hook-xyz", json=False)
    assert _cmd_hooks_info(ns) == 1
    assert "not found" in capsys.readouterr().out.lower()


def test_hooks_install_deprecated_exits_2(capsys) -> None:
    from oclaw.runtime.operations.hooks_cmd import _cmd_hooks_install

    ns = argparse.Namespace(spec="foo@1.0.0", link=False, pin=False)
    assert _cmd_hooks_install(ns) == 2
    err = capsys.readouterr().err
    assert "deprecated" in err.lower() and "foo@1.0.0" in err


def test_hooks_install_missing_spec_exits_1(capsys) -> None:
    from oclaw.runtime.operations.hooks_cmd import _cmd_hooks_install

    assert _cmd_hooks_install(argparse.Namespace(spec="", link=False, pin=False)) == 1
    assert "missing" in capsys.readouterr().err.lower()


def test_hooks_update_deprecated_exits_2(capsys) -> None:
    from oclaw.runtime.operations.hooks_cmd import _cmd_hooks_update

    assert _cmd_hooks_update(argparse.Namespace(hook_id="pack-a", all=False, dry_run=True)) == 2
    err = capsys.readouterr().err
    assert "deprecated" in err.lower()


def test_main_hooks_install_invocation(capsys) -> None:
    from oclaw.runtime.operations import main as cli_main

    code = cli_main(["hooks", "install", "some-spec@1"])
    assert code == 2
    assert "deprecated" in capsys.readouterr().err.lower()


def test_main_hooks_list_invocation(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    from oclaw.runtime.operations import main as cli_main

    old = sys.stdout
    buf = StringIO()
    try:
        sys.stdout = buf
        code = cli_main(["hooks", "list", "--json", "--workspace", str(tmp_path)])
    finally:
        sys.stdout = old
    assert code == 0
    obj = json.loads(buf.getvalue())
    assert "hooks" in obj


def test_resolve_cli_workspace_uses_env_over_cwd(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    expected = tmp_path / "repo-root"
    expected.mkdir(parents=True)
    monkeypatch.setenv("OCLAW_WORKSPACE", str(expected))
    from oclaw.runtime.operations.hooks_cmd import _resolve_cli_workspace

    ns = argparse.Namespace(workspace="")
    assert _resolve_cli_workspace(ns) == str(expected)


def test_resolve_cli_workspace_falls_back_to_workspace_root(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OCLAW_WORKSPACE", raising=False)
    monkeypatch.setenv("OPS_WORKSPACE_ROOT", str(tmp_path))
    from oclaw.runtime.operations.hooks_cmd import _resolve_cli_workspace

    ns = argparse.Namespace(workspace="")
    assert _resolve_cli_workspace(ns) == str(tmp_path.resolve())
