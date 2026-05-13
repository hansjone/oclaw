from __future__ import annotations

from runtime.direct_loop import _split_reasoning_and_body


def test_split_reasoning_extracts_thinking_tags() -> None:
    chunks, body = _split_reasoning_and_body("<thinking>\ninner\n</thinking>\nvisible")
    assert chunks == ["inner"]
    assert body == "visible"


def test_split_reasoning_extracts_thought_tags() -> None:
    chunks, body = _split_reasoning_and_body("<thought>x</thought>after")
    assert chunks == ["x"]
    assert body == "after"


def test_split_reasoning_explicit_when_no_tags() -> None:
    chunks, body = _split_reasoning_and_body("body only", explicit_reasoning="  rc  ")
    assert chunks == ["rc"]
    assert body == "body only"


def test_split_reasoning_antml_optional_prefix() -> None:
    raw = "<antml:thinking>\nZ\n</antml:thinking>\nok"
    chunks, body = _split_reasoning_and_body(raw)
    assert chunks == ["Z"]
    assert body == "ok"
