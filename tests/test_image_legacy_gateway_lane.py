from __future__ import annotations

import json

import pytest

from svc.llm.image_http_common import (
    dashscope_multimodal_http_ok,
    dashscope_native_multimodal_url_from_compatible_base,
    extract_text_and_images,
)
from svc.llm.image_http_common import build_extract_diag_empty
from svc.llm.image_legacy_client import (
    collect_legacy_lane_images_from_attachments,
    collect_legacy_lane_images_with_session_fallback,
    legacy_image_assistant_body_with_placeholder,
    legacy_image_turn_bundle,
    normalize_legacy_output_image_urls,
    parse_message_attachments_json,
)
from svc.llm.image_legacy_client import _http_content_blocks
from svc.llm.image_legacy_client import _openai_compatible_vision_content


def test_openai_compatible_vision_has_type_per_part() -> None:
    """compatible-mode /chat/completions expects type on each content element."""
    b = _openai_compatible_vision_content(
        ["https://example.invalid/a.png", "data:image/png;base64,abcd"],
        "prompt",
    )
    assert len(b) == 3
    assert b[0]["type"] == "image_url" and "url" in b[0]["image_url"]
    assert b[1]["type"] == "image_url"
    assert b[2]["type"] == "text" and b[2]["text"] == "prompt"


def test_http_content_blocks_multi_image_then_text() -> None:
    """DashScope samples: one user message, content = N × {"image": url} then {"text": ...}."""
    b = _http_content_blocks(
        [
            "https://example.invalid/a.png",
            "https://example.invalid/b.png",
        ],
        "合成说明",
        typed=False,
    )
    assert b == [
        {"image": "https://example.invalid/a.png"},
        {"image": "https://example.invalid/b.png"},
        {"text": "合成说明"},
    ]


def test_normalize_legacy_output_dict_image_parts() -> None:
    u = "https://dashscope-result-sz.oss-cn-shenzhen.aliyuncs.com/x.png?Expires=1"
    assert normalize_legacy_output_image_urls([{"image": u}]) == [u]
    assert normalize_legacy_output_image_urls([{"image_url": {"url": u}}]) == [u]


def test_legacy_turn_bundle_coerces_dict_images_to_attachments() -> None:
    ok, text, att = legacy_image_turn_bundle(
        {"ok": True, "text": "", "images": [{"image": "https://example.invalid/a.png"}]}
    )
    assert ok is True
    assert len(att) == 1
    assert att[0]["type"] == "image_url"
    assert att[0]["url"] == "https://example.invalid/a.png"


def test_dashscope_native_url_from_compatible_base() -> None:
    assert (
        dashscope_native_multimodal_url_from_compatible_base(
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        == "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    )
    assert (
        dashscope_native_multimodal_url_from_compatible_base("https://example.com/openai/v1") is None
    )


def test_collect_legacy_lane_images_image_url() -> None:
    atts = [{"type": "image_url", "url": "https://example.invalid/x.png"}]
    assert collect_legacy_lane_images_from_attachments(atts) == ["https://example.invalid/x.png"]


def test_collect_legacy_lane_images_raw_base64() -> None:
    atts = [{"type": "input_image", "mime": "image/png", "image_base64": "SGVsbG8="}]
    got = collect_legacy_lane_images_from_attachments(atts)
    assert len(got) == 1
    assert got[0].startswith("data:image/png;base64,")


def test_legacy_turn_bundle_text_only_success() -> None:
    ok, text, att = legacy_image_turn_bundle({"ok": True, "text": "caption only", "images": []})
    assert ok is True
    assert text == "caption only"
    assert att == []


def test_legacy_image_assistant_placeholder_zh_en() -> None:
    produced = [{"type": "image_ref", "attachment_id": "a" * 64}]
    assert "附件" in legacy_image_assistant_body_with_placeholder(
        lang="zh", body_text="", produced=produced
    )
    assert "attachment" in legacy_image_assistant_body_with_placeholder(
        lang="en", body_text="", produced=produced
    ).lower()
    assert legacy_image_assistant_body_with_placeholder(lang="zh", body_text="x", produced=produced) == "x"


def test_legacy_turn_bundle_upstream_error() -> None:
    ok, text, att = legacy_image_turn_bundle({"ok": False, "error": "rate"})
    assert ok is False
    assert "rate" in text
    assert att == []


def test_extract_harvests_nested_https_under_message() -> None:
    url = "https://cdn.example.invalid/generated.png"
    text, images = extract_text_and_images(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "metadata": {"preview_image": url},
                    }
                }
            ]
        }
    )
    assert text == ""
    assert images == [url]


def test_build_extract_diag_top_level_openai_choices() -> None:
    d = build_extract_diag_empty(
        {
            "choices": [],
            "model": "x",
        }
    )
    assert d.get("choices_len") == 0


def test_legacy_turn_bundle_includes_provider_redacted() -> None:
    ok, msg, att = legacy_image_turn_bundle(
        {
            "ok": True,
            "text": "",
            "images": [],
            "extract_diag": {"choices_len": 0},
            "provider_response_redacted": '{"choices":[]}',
        }
    )
    assert ok is False
    assert "provider_json=" in msg
    assert att == []


def test_legacy_turn_bundle_empty_ok_response_fails() -> None:
    ok, text, att = legacy_image_turn_bundle({"ok": True, "text": "", "images": []})
    assert ok is False
    assert att == []


def test_extract_text_and_images_dashscope_output_wrapper() -> None:
    """Native multimodal HTTP wraps ``choices`` under ``output`` (not top-level OpenAI shape)."""
    url = "https://dashscope-result-hz.oss-cn-hangzhou.aliyuncs.com/x.png?Expires=1"
    payload = {
        "status_code": 200,
        "request_id": "959afba6-544e-487e-b58a-6bd9fea97xxx",
        "code": "",
        "message": "",
        "output": {
            "text": None,
            "finish_reason": None,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": [{"image": url}],
                    },
                }
            ],
            "audio": None,
        },
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "image_count": 1,
            "width": 2048,
            "height": 2048,
        },
    }
    text, images = extract_text_and_images(payload)
    assert text == ""
    assert images == [url]
    assert dashscope_multimodal_http_ok(payload)[0] is True


def test_extract_text_and_images_content_dict_not_list() -> None:
    """Some gateways return a single object for ``message.content`` instead of an array."""
    url = "https://dashscope-result-hz.oss-cn-hangzhou.aliyuncs.com/out.png"
    text, images = extract_text_and_images(
        {
            "output": {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": {"image": url},
                        }
                    }
                ]
            }
        }
    )
    assert text == ""
    assert images == [url]


def test_extract_text_and_images_messages_fallback() -> None:
    text, images = extract_text_and_images(
        {
            "output": {
                "messages": [
                    {"role": "user", "content": "x"},
                    {
                        "role": "assistant",
                        "content": [{"image": "https://example.invalid/gen.png"}],
                    },
                ]
            }
        }
    )
    assert images == ["https://example.invalid/gen.png"]


def test_extract_text_and_images_typed_image_url_part() -> None:
    text, images = extract_text_and_images(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": "https://example.invalid/v.png"},
                            }
                        ]
                    }
                }
            ]
        }
    )
    assert images == ["https://example.invalid/v.png"]


def test_dashscope_envelope_rejects_non_success_code() -> None:
    ok, msg = dashscope_multimodal_http_ok({"code": "InvalidParameter", "message": "bad"})
    assert ok is False
    assert "bad" in msg


def test_extract_text_and_images_openai_top_level_unchanged() -> None:
    text, images = extract_text_and_images(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "hi"},
                            {"image": "https://example.invalid/a.jpg"},
                        ]
                    }
                }
            ]
        }
    )
    assert "hi" in text
    assert images == ["https://example.invalid/a.jpg"]


def test_parse_message_attachments_json_string_list() -> None:
    raw = json.dumps([{"type": "image_url", "url": "https://example.invalid/z.png"}])
    got = parse_message_attachments_json(raw)
    assert len(got) == 1 and got[0]["url"] == "https://example.invalid/z.png"


class _FakeHistMsg:
    __slots__ = ("role", "attachments")

    def __init__(self, role: str, attachments: object) -> None:
        self.role = role
        self.attachments = attachments


class _FakeHistStore:
    def __init__(self, msgs: list[_FakeHistMsg]) -> None:
        self._msgs = msgs

    def get_messages(self, session_id: str, limit: int = 200) -> list[_FakeHistMsg]:
        _ = session_id
        return self._msgs[-limit:] if len(self._msgs) > limit else list(self._msgs)


def test_session_fallback_prefers_latest_assistant_images() -> None:
    """Newest assistant row with images wins over older user uploads."""
    msgs = [
        _FakeHistMsg(
            "user",
            json.dumps([{"type": "image_url", "url": "https://example.invalid/old-user.png"}]),
        ),
        _FakeHistMsg(
            "assistant",
            json.dumps([{"type": "image_url", "url": "https://example.invalid/from-assistant.png"}]),
        ),
        _FakeHistMsg("user", "null"),
    ]
    store = _FakeHistStore(msgs)
    imgs, src = collect_legacy_lane_images_with_session_fallback(
        store=store,
        session_id="s1",
        attachments=[],
    )
    assert src == "assistant_history"
    assert imgs == ["https://example.invalid/from-assistant.png"]


def test_session_fallback_user_history_when_no_assistant_images() -> None:
    msgs = [
        _FakeHistMsg(
            "user",
            json.dumps([{"type": "image_url", "url": "https://example.invalid/only-user.png"}]),
        ),
        _FakeHistMsg("assistant", "[]"),
        _FakeHistMsg("user", "null"),
    ]
    store = _FakeHistStore(msgs)
    imgs, src = collect_legacy_lane_images_with_session_fallback(
        store=store,
        session_id="s1",
        attachments=[],
    )
    assert src == "user_history"
    assert imgs == ["https://example.invalid/only-user.png"]


def test_session_fallback_disabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIA_IMAGE_SPECIALIST_SESSION_IMAGE_FALLBACK", "0")
    msgs = [
        _FakeHistMsg(
            "assistant",
            json.dumps([{"type": "image_url", "url": "https://example.invalid/a.png"}]),
        ),
        _FakeHistMsg("user", "null"),
    ]
    store = _FakeHistStore(msgs)
    imgs, src = collect_legacy_lane_images_with_session_fallback(
        store=store,
        session_id="s1",
        attachments=[],
    )
    assert src == ""
    assert imgs == []


def test_session_fallback_current_attachments_skip_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIA_IMAGE_SPECIALIST_SESSION_IMAGE_FALLBACK", raising=False)
    msgs = [
        _FakeHistMsg(
            "assistant",
            json.dumps([{"type": "image_url", "url": "https://example.invalid/hist.png"}]),
        ),
        _FakeHistMsg("user", "null"),
    ]
    store = _FakeHistStore(msgs)
    imgs, src = collect_legacy_lane_images_with_session_fallback(
        store=store,
        session_id="s1",
        attachments=[{"type": "image_url", "url": "https://example.invalid/current.png"}],
    )
    assert src == "current"
    assert imgs == ["https://example.invalid/current.png"]
