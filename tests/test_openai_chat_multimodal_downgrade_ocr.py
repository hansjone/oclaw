from __future__ import annotations

from unittest.mock import patch

from oclaw.platform.llm.transports.openai_chat_completions import (
    _flatten_message_content_for_text_gateway,
    _normalize_messages_for_text_only_gateway,
)


def test_text_only_downgrade_injects_ocr_when_vision_lane_ok(monkeypatch) -> None:
    monkeypatch.setenv("AIA_MULTIMODAL_DOWNGRADE_OCR", "1")
    monkeypatch.setenv("AIA_OCR_BASE_URL", "https://ocr.example/v1")
    monkeypatch.setenv("AIA_OCR_API_KEY", "k")
    monkeypatch.setenv("AIA_OCR_MODEL", "vl-test")

    def fake_send(*, images, prompt, **kwargs):
        _ = (images, prompt, kwargs)
        return {"ok": True, "text": "HELLO_FROM_PIC"}

    with patch("oclaw.platform.llm.image_ocr_client.send_ocr_image_messages", fake_send):
        content = [
            {"type": "text", "text": "请看图"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
        ]
        flat = _flatten_message_content_for_text_gateway(content)
    assert "HELLO_FROM_PIC" in flat
    assert "【图片内容·OCR】" in flat
    assert "纯文本" in flat
    assert "请看图" in flat
    assert "无法直接读图" in flat


def test_text_only_downgrade_falls_back_when_ocr_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AIA_MULTIMODAL_DOWNGRADE_OCR", "0")
    monkeypatch.setenv("AIA_OCR_BASE_URL", "https://ocr.example/v1")
    monkeypatch.setenv("AIA_OCR_API_KEY", "k")
    monkeypatch.setenv("AIA_OCR_MODEL", "vl-test")

    content = [
        {"type": "text", "text": "hi"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
    ]
    flat = _flatten_message_content_for_text_gateway(content)
    assert "【图片】本消息含图片" in flat
    assert "hi" in flat


def test_normalize_messages_uses_ocr_flatten(monkeypatch) -> None:
    monkeypatch.setenv("AIA_MULTIMODAL_DOWNGRADE_OCR", "1")
    monkeypatch.setenv("AIA_OCR_BASE_URL", "https://ocr.example/v1")
    monkeypatch.setenv("AIA_OCR_API_KEY", "k")
    monkeypatch.setenv("AIA_OCR_MODEL", "vl-test")

    def fake_send(*, images, prompt, **kwargs):
        _ = (images, prompt, kwargs)
        return {"ok": True, "text": "X"}

    with patch("oclaw.platform.llm.image_ocr_client.send_ocr_image_messages", fake_send):
        out = _normalize_messages_for_text_only_gateway(
            [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://x/y.png"}}]}]
        )
    assert len(out) == 1
    assert out[0]["role"] == "user"
    assert "X" in str(out[0]["content"])
    assert isinstance(out[0]["content"], str)
