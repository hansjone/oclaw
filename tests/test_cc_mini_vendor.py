from __future__ import annotations

import os

import pytest

from svc.integrations import cc_mini_vendor as m


def test_cc_mini_pythonpath_prepends_src_when_available() -> None:
    if not m.cc_mini_available():
        pytest.skip("vendor/cc-mini submodule not initialized")
    env = m.cc_mini_pythonpath_env({"PYTHONPATH": "/existing"})
    head, *rest = env["PYTHONPATH"].split(os.pathsep)
    assert head == str(m.cc_mini_src_dir())
    assert "/existing" in env["PYTHONPATH"]


def test_run_cc_mini_cli_missing_raises() -> None:
    # If someone deletes only engine.py this still triggers missing tree in practice;
    # we only assert the error type when the whole checkout is absent.
    if m.cc_mini_available():
        pytest.skip("cc-mini present")
    with pytest.raises(FileNotFoundError) as ei:
        m.run_cc_mini_cli(["--help"])
    assert "git submodule" in str(ei.value).lower() or "cc-mini" in str(ei.value).lower()
