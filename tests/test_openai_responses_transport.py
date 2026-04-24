from __future__ import annotations

from oclaw.platform.llm.transports.openai_responses import parse_openai_responses_stream_events


def test_openai_responses_stream_parses_text_deltas_and_final_response_tool_calls() -> None:
    events = [
        {"type": "response.created"},
        {"type": "response.output_text.delta", "delta": "Hel"},
        {"type": "response.output_text.delta", "delta": "lo"},
        {
            "type": "response.completed",
            "response": {
                "id": "resp_1",
                "output_text": "Hello",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "query_route",
                        "arguments": {"destination": "1.1.1.1"},
                    }
                ],
            },
        },
    ]
    buf: list[str] = []
    text, tool_calls, final_resp = parse_openai_responses_stream_events(events, on_token=buf.append)
    assert text == "Hello"
    assert "".join(buf) == "Hello"
    assert final_resp and final_resp.get("id") == "resp_1"
    assert len(tool_calls) == 1
    assert tool_calls[0].id == "call_1"
    assert tool_calls[0].name == "query_route"
    assert tool_calls[0].arguments.get("destination") == "1.1.1.1"

