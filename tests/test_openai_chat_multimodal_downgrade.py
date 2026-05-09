from __future__ import annotations

from oclaw.platform.llm.transports.openai_chat_completions import (
    _is_text_only_gateway_error,
    _messages_contain_list_with_image,
    _should_proactively_downgrade_multimodal_messages,
    _wire_error_message,
)


def test_text_only_gateway_error_matches_deepseek_deserialize() -> None:
    msg = "messages[1]: unknown variant image_url, expected text at line 1 column 74402"
    assert _is_text_only_gateway_error(msg)


def test_text_only_gateway_error_from_nested_body() -> None:
    snippet = '{"error":{"message":"Failed to deserialize: unknown variant image_url, expected text"}}'
    assert _is_text_only_gateway_error(snippet)


def test_messages_contain_list_with_image() -> None:
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "hi"}, {"type": "image_url", "image_url": {"url": "x"}}]},
    ]
    assert _messages_contain_list_with_image(msgs)
    assert _should_proactively_downgrade_multimodal_messages(msgs, model="deepseek-chat", base_url="https://api.example.com/")
    assert not _should_proactively_downgrade_multimodal_messages(
        msgs, model="gpt-4o-mini", base_url="https://api.openai.com/v1/"
    )


class _Bare400(Exception):
    def __init__(self) -> None:
        super().__init__("Error code: 400")
        self.body = {
            "error": {
                "message": "Failed to deserialize: messages[1]: unknown variant image_url, expected text",
                "type": "invalid_request_error",
            },
        }


def test_wire_error_message_includes_exception_body_json() -> None:
    wired = _wire_error_message(_Bare400())
    assert _is_text_only_gateway_error(wired)
