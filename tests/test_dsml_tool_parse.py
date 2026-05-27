from __future__ import annotations

from runtime.dsml_tool_parse import (
    DeepSeekTextFilter,
    normalize_dsml_markup,
    strip_first_dsml_tool_calls_block,
    try_parse_deepseek_v4_dsml_tool_calls,
    try_parse_dsml_tool_calls_from_fields,
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


def test_promote_combined_when_dsml_only_in_reasoning() -> None:
    from runtime.dsml_tool_parse import try_promote_dsml_from_fields

    p = "\uFF5C"
    reasoning = (
        f"<{p}{p}DSML{p}{p}tool_calls>\n"
        f"<{p}{p}DSML{p}{p}invoke name=\"run_command\">\n"
        f"<{p}{p}DSML{p}{p}parameter name=\"command\" string=\"true\">echo</{p}{p}DSML{p}{p}parameter>\n"
        f"</{p}{p}DSML{p}{p}invoke>\n"
        f"</{p}{p}DSML{p}{p}tool_calls>"
    )
    parsed, clean_c, clean_r = try_promote_dsml_from_fields(content="让我检查一下。", reasoning_content=reasoning)
    assert parsed is not None and len(parsed) == 1
    assert parsed[0].name == "run_command"
    assert "检查一下" in clean_c
    assert "DSML" not in clean_r


def test_parse_double_fullwidth_pipe_variant() -> None:
    p = "\uFF5C"
    text = (
        f"<{p}{p}DSML{p}{p}tool_calls>\n"
        f"<{p}{p}DSML{p}{p}invoke name=\"run_command\">\n"
        f"<{p}{p}DSML{p}{p}parameter name=\"command\" string=\"true\">"
        "echo %HTTP_PROXY% & echo %HTTPS_PROXY%</"
        f"{p}{p}DSML{p}{p}parameter>\n"
        f"</{p}{p}DSML{p}{p}invoke>\n"
        f"</{p}{p}DSML{p}{p}tool_calls>"
    )
    calls = try_parse_deepseek_v4_dsml_tool_calls(text)
    assert calls is not None and len(calls) == 1
    assert calls[0].name == "run_command"
    assert "HTTP_PROXY" in str(calls[0].arguments.get("command") or "")


def test_parse_spaced_pipe_variant_from_screenshot() -> None:
    text = (
        "< | | DSML | | tool_calls>\n"
        '< | | DSML | | invoke name="read_file">\n'
        '< | | DSML | | parameter name="path" string="true">_local/x.json</ | | DSML | | parameter>\n'
        "</ | | DSML | | invoke>\n"
        '< | | DSML | | invoke name="grep">\n'
        '< | | DSML | | parameter name="pattern" string="true">foo</ | | DSML | | parameter>\n'
        "</ | | DSML | | invoke>\n"
        "</ | | DSML | | tool_calls>"
    )
    calls = try_parse_deepseek_v4_dsml_tool_calls(text)
    assert calls is not None and len(calls) == 2
    assert calls[0].name == "read_file"
    assert calls[0].arguments == {"path": "_local/x.json"}
    assert calls[1].name == "grep"


def test_stream_filter_spaced_pipe_variant() -> None:
    text = (
        "prefix\n"
        "< | | DSML | | tool_calls>\n"
        '< | | DSML | | invoke name="run_command"></ | | DSML | | invoke>\n'
        "</ | | DSML | | tool_calls>"
    )
    filt = DeepSeekTextFilter()
    visible = ""
    for part in filt.push(text):
        visible += part
    for part in filt.flush():
        visible += part
    assert "prefix" in visible
    assert "DSML" not in visible
    recovered = filt.recovered_tool_calls()
    assert len(recovered) == 1
    assert recovered[0].name == "run_command"


def test_parse_function_calls_wrapper_v32() -> None:
    text = (
        "<||DSML||function_calls>\n"
        "<||DSML||invoke name=\"get_weather\">\n"
        "<||DSML||parameter name=\"location\" string=\"true\">Tokyo</||DSML||parameter>\n"
        "</||DSML||invoke>\n"
        "</||DSML||function_calls>"
    )
    calls = try_parse_deepseek_v4_dsml_tool_calls(text)
    assert calls is not None and len(calls) == 1
    assert calls[0].name == "get_weather"
    assert calls[0].arguments == {"location": "Tokyo"}


def test_parse_json_invoke_body() -> None:
    text = (
        "<||DSML||tool_calls>\n"
        "<||DSML||invoke name=\"get_weather\">\n"
        '{"location": "Tokyo", "count": 5}\n'
        "</||DSML||invoke>\n"
        "</||DSML||tool_calls>"
    )
    calls = try_parse_deepseek_v4_dsml_tool_calls(text)
    assert calls is not None and len(calls) == 1
    assert calls[0].arguments == {"location": "Tokyo", "count": 5}


def test_parse_from_reasoning_content() -> None:
    dsml = (
        "<||DSML||tool_calls>\n"
        "<||DSML||invoke name=\"run_command\"></||DSML||invoke>\n"
        "</||DSML||tool_calls>"
    )
    parsed, clean_content, clean_reasoning = try_parse_dsml_tool_calls_from_fields(
        content="summary text",
        reasoning_content=f"thinking\n{dsml}",
    )
    assert parsed is not None and len(parsed) == 1
    assert parsed[0].name == "run_command"
    assert clean_content == "summary text"
    assert "tool_calls" not in clean_reasoning


def test_stream_filter_hides_dsml_and_recovers() -> None:
    p = "\uFF5c"
    full = (
        f"visible prefix\n"
        f"<{p}DSML{p}tool_calls>\n"
        f"<{p}DSML{p}invoke name=\"run_command\">\n"
        f"<{p}DSML{p}parameter name=\"command\" string=\"true\">echo hi</{p}DSML{p}parameter>\n"
        f"</{p}DSML{p}invoke>\n"
        f"</{p}DSML{p}tool_calls>"
    )
    filt = DeepSeekTextFilter()
    visible = ""
    chunk_size = 7
    for i in range(0, len(full), chunk_size):
        for part in filt.push(full[i : i + chunk_size]):
            visible += part
    for part in filt.flush():
        visible += part
    assert "visible prefix" in visible
    assert "DSML" not in visible
    recovered = filt.recovered_tool_calls()
    assert len(recovered) == 1
    assert recovered[0].name == "run_command"
    assert recovered[0].arguments == {"command": "echo hi"}
