from __future__ import annotations

from svc.llm.transports.anthropic_messages import parse_anthropic_stream_events


def test_anthropic_stream_parses_text_and_tool_use() -> None:
    events = [
        {"type": "message_start"},
        {"type": "content_block_start", "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi "}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "there"}},
        {"type": "content_block_stop"},
        {"type": "content_block_start", "content_block": {"type": "tool_use", "id": "toolu_1", "name": "query_route", "input": {}}},
        {"type": "content_block_delta", "delta": {"type": "input_json_delta", "partial_json": "{\"destination\":\"1.1.1.1\"}"}},
        {"type": "content_block_stop"},
        {"type": "message_stop"},
    ]
    buf: list[str] = []
    text, tool_calls = parse_anthropic_stream_events(events, on_token=buf.append)
    assert text == "Hi there"
    assert "".join(buf) == "Hi there"
    assert len(tool_calls) == 1
    tc = tool_calls[0]
    assert tc.id == "toolu_1"
    assert tc.name == "query_route"
    assert tc.arguments.get("destination") == "1.1.1.1"

