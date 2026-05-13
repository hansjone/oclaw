from __future__ import annotations

from runtime.command_parser import parse_internal_command


def test_parse_internal_command_basic() -> None:
    got = parse_internal_command("/new")
    assert got is not None
    assert got.action == "new"
    assert got.command == "new"
    assert got.args == ()


def test_parse_internal_command_alias_and_args() -> None:
    got = parse_internal_command("reset now force")
    assert got is not None
    assert got.action == "reset"
    assert got.command == "reset"
    assert got.args == ("now", "force")


def test_parse_internal_command_localized_alias() -> None:
    got = parse_internal_command("／重置 会话")
    assert got is not None
    assert got.action == "reset"
    assert got.command == "重置"
    assert got.args == ("会话",)

