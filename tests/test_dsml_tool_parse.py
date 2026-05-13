from __future__ import annotations

from runtime.dsml_tool_parse import (
    normalize_dsml_markup,
    strip_first_dsml_tool_calls_block,
    try_parse_deepseek_v4_dsml_tool_calls,
)


def test_normalize_ascii_pipe_variant() -> None:
    raw = "<||DSML||tool_calls>x</||DSML||tool_calls>"
    n = normalize_dsml_markup(raw)
    assert "\uFF5cDSML\uFF5c" in n


def test_parse_official_delimiters_single_invoke() -> None:
    p = "\uFF5c"
    text = (
        f"prefix\n<{p}DSML{p}tool_calls>\n"
        f"<{p}DSML{p}invoke name=\"run_command\">\n"
        f"<{p}DSML{p}parameter name=\"command\" string=\"true\">echo hi</{p}DSML{p}parameter>\n"
        f"</{p}DSML{p}invoke>\n"
        f"</{p}DSML{p}tool_calls>\nsuffix"
    )
    calls = try_parse_deepseek_v4_dsml_tool_calls(text)
    assert calls is not None and len(calls) == 1
    assert calls[0].name == "run_command"
    assert calls[0].arguments == {"command": "echo hi"}


def test_parse_pipe_variant_and_json_param() -> None:
    text = (
        "<||DSML||tool_calls>\n"
        "<||DSML||invoke name=\"echo_tool\">\n"
        "<||DSML||parameter name=\"x\" string=\"false\">42</||DSML||parameter>\n"
        "</||DSML||invoke>\n"
        "</||DSML||tool_calls>"
    )
    calls = try_parse_deepseek_v4_dsml_tool_calls(text)
    assert calls is not None and len(calls) == 1
    assert calls[0].name == "echo_tool"
    assert calls[0].arguments["x"] == 42


def test_parse_two_invokes() -> None:
    text = (
        "<||DSML||tool_calls>\n"
        "<||DSML||invoke name=\"a\"></||DSML||invoke>\n"
        "<||DSML||invoke name=\"b\"></||DSML||invoke>\n"
        "</||DSML||tool_calls>"
    )
    calls = try_parse_deepseek_v4_dsml_tool_calls(text)
    assert calls is not None and [c.name for c in calls] == ["a", "b"]


def test_strip_removes_block_keeps_prefix() -> None:
    text = "hello\n<||DSML||tool_calls>\n<||DSML||invoke name=\"x\"></||DSML||invoke>\n</||DSML||tool_calls>\n"
    s = strip_first_dsml_tool_calls_block(text)
    assert s is not None
    assert "hello" in s
    assert "tool_calls" not in s


def test_malformed_returns_none() -> None:
    assert try_parse_deepseek_v4_dsml_tool_calls("<||DSML||tool_calls>broken") is None
