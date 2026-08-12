# -*- coding: utf-8 -*-
"""Unit tests for execManagedNe arg normalize / detect helpers."""
from __future__ import annotations

from runtime.chat.exec_managed_ne_guard import (
    is_batch_exec_args,
    is_exec_managed_ne_tool,
    normalize_exec_managed_ne_args,
)


def test_is_exec_managed_ne_tool_aliases() -> None:
    assert is_exec_managed_ne_tool("mcp__netx__execManagedNe")
    assert is_exec_managed_ne_tool("netx_exec_managed_ne")
    assert not is_exec_managed_ne_tool("mcp__netx__listCliTargets")


def test_is_batch_exec_args() -> None:
    assert is_batch_exec_args({"ne_ids": ["a", "b"], "commands": ["show version"]})
    assert is_batch_exec_args({"ume_ne_ids": ["u1"]})
    assert is_batch_exec_args({"targets": [{"ne_id": "x"}]})
    assert not is_batch_exec_args({"ne_id": "x", "commands": ["show version"]})
    assert not is_batch_exec_args({"ne_ids": []})


def test_normalize_exec_managed_ne_args_defaults_and_clamps() -> None:
    assert normalize_exec_managed_ne_args({})["read_timeout_sec"] == 60
    assert normalize_exec_managed_ne_args({"read_timeout_sec": 5})["read_timeout_sec"] == 10
    assert normalize_exec_managed_ne_args({"read_timeout_sec": 999})["read_timeout_sec"] == 120
    assert normalize_exec_managed_ne_args({"read_timeout_sec": 90})["read_timeout_sec"] == 90
