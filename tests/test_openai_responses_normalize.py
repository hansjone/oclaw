from __future__ import annotations

import httpx
from openai import BadRequestError

from oclaw.platform.llm.transports.openai_responses import OpenAIResponsesModel, _is_input_messages_validation_error


def test_input_messages_validation_detects_body_not_str_exc() -> None:
    """OpenAI SDK ``str(exc)`` is usually only ``Error code: 400``; gateway detail is in ``body``."""
    req = httpx.Request("POST", "http://example.invalid/v1/responses")
    resp = httpx.Response(400, request=req)
    body = {
        "message": (
            "Input should be 'user': input.messages.0.role & Input should be a valid list: "
            "input.messages.0.content"
        ),
        "type": "invalid_request_error",
        "code": "invalid_parameter_error",
        "param": None,
    }
    exc = BadRequestError("Error code: 400", response=resp, body=body)
    assert "input.messages" not in str(exc).lower()
    assert _is_input_messages_validation_error(exc) is True


def test_strip_leading_system_to_instructions_kw() -> None:
    msgs = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"},
    ]
    txt, tail = OpenAIResponsesModel._strip_leading_system_messages(msgs)
    assert txt == "You are helpful."
    assert tail == [{"role": "user", "content": "Hi"}]


def test_normalize_default_responses_parts_and_openai_envelope() -> None:
    msgs = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "https://example.invalid/x.png"}},
                {"type": "text", "text": "what?"},
            ],
        }
    ]
    out = OpenAIResponsesModel._normalize_messages(msgs)
    assert len(out) == 1
    assert out[0]["type"] == "message"
    assert out[0]["role"] == "user"
    cc = out[0]["content"]
    assert isinstance(cc, list)
    assert any(
        x.get("type") == "input_image"
        and isinstance(x.get("image_url"), str)
        and x.get("detail") == "auto"
        for x in cc
    )
    assert any(x.get("type") == "input_text" and x.get("text") == "what?" for x in cc)


def test_normalize_nested_chat_parts_opt_in() -> None:
    msgs = [
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": "https://example.invalid/x.png"}}],
        }
    ]
    out = OpenAIResponsesModel._normalize_messages(
        msgs, envelope_openai_message=False, content_chat_completions_parts=True
    )
    assert "type" not in out[0]
    assert out[0]["role"] == "user"
    assert any(x.get("type") == "image_url" for x in out[0]["content"])


def test_normalize_dashscope_shorthand_image_text_blocks() -> None:
    msgs = [
        {"role": "user", "content": [{"image": "https://example.invalid/y.png"}, {"text": "caption"}]},
    ]
    out = OpenAIResponsesModel._normalize_messages(msgs)
    assert out[0]["type"] == "message"
    assert out[0]["role"] == "user"
    parts = out[0]["content"]
    assert isinstance(parts, list)
    imgs = [p for p in parts if isinstance(p, dict) and p.get("type") == "input_image"]
    assert len(imgs) == 1 and imgs[0].get("detail") == "auto"
    txts = [p for p in parts if isinstance(p, dict) and p.get("type") == "input_text"]
    assert any("caption" in str(p.get("text")) for p in txts)


def test_responses_input_candidates_cover_flat_and_nested() -> None:
    msgs = [{"role": "user", "content": "hi"}]
    flat = OpenAIResponsesModel._responses_input_candidates(
        msgs, flat_responses=True, prefer_envelope=True, prefer_chat_parts=False
    )
    assert len(flat) >= 1
    nested = OpenAIResponsesModel._responses_input_candidates(
        msgs, flat_responses=False, prefer_envelope=True, prefer_chat_parts=False
    )
    tags = [t for t, _ in nested]
    assert any("_messages" in t for t in tags)
    assert any("_flat_input" in t for t in tags)


def test_responses_input_candidates_primary_combo_first() -> None:
    msgs = [{"role": "user", "content": "hi"}]
    nested = OpenAIResponsesModel._responses_input_candidates(
        msgs, flat_responses=False, prefer_envelope=True, prefer_chat_parts=False
    )
    assert nested[0][0] == "e1c0_messages"
    assert nested[1][0] == "e1c0_flat_input"

    nested2 = OpenAIResponsesModel._responses_input_candidates(
        msgs, flat_responses=False, prefer_envelope=False, prefer_chat_parts=True
    )
    assert nested2[0][0] == "e0c1_messages"
    assert nested2[1][0] == "e0c1_flat_input"


def test_normalize_agent_messages_style_input_image() -> None:
    """Matches ``build_llm_messages`` last-turn multimodal blocks (``input_image`` + ``image_base64``)."""
    msgs = [
        {
            "role": "user",
            "content": [
                {"type": "input_image", "image_base64": "SGk=", "mime": "image/png"},
                {"type": "text", "text": "what is this"},
            ],
        }
    ]
    out = OpenAIResponsesModel._normalize_messages(msgs)
    assert len(out) == 1
    assert out[0]["type"] == "message"
    parts = out[0]["content"]
    imgs = [p for p in parts if isinstance(p, dict) and p.get("type") == "input_image"]
    assert len(imgs) == 1
    assert imgs[0]["image_url"].startswith("data:image/png;base64,")
    assert imgs[0].get("detail") == "auto"
    txts = [p for p in parts if isinstance(p, dict) and p.get("type") == "input_text"]
    assert any(p.get("text") == "what is this" for p in txts)

    chat_parts = OpenAIResponsesModel._normalize_messages(
        msgs, envelope_openai_message=False, content_chat_completions_parts=True
    )
    cp = chat_parts[0]["content"]
    assert any(
        isinstance(p, dict) and p.get("type") == "image_url" and "base64" in str(p.get("image_url", {}).get("url"))
        for p in cp
    )
    assert any(p.get("type") == "text" and p.get("text") == "what is this" for p in cp)


def test_image_legacy_compatible_mode_uses_image_url_parts() -> None:
    from oclaw.platform.llm.image_legacy_client import _openai_compatible_vision_content

    cc = _openai_compatible_vision_content(["data:image/jpeg;base64,SGk="], "go")
    assert cc[-1]["type"] == "text"
    assert cc[-1]["text"] == "go"
    assert cc[0]["type"] == "image_url"
