from __future__ import annotations

from oclaw.runtime.chat.model_path_audit import ensure_no_tool_or_embedded_image_payload


def test_audit_accepts_plain_system_user_messages() -> None:
    ensure_no_tool_or_embedded_image_payload(
        path="unit.ok",
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
        ],
    )


def test_audit_degrades_tool_role() -> None:
    msgs = [
        {"role": "assistant", "content": "a"},
        {"role": "tool", "content": '{"ok":true}'},
    ]
    ensure_no_tool_or_embedded_image_payload(path="unit.tool", messages=msgs)
    assert msgs[1]["role"] == "assistant"
    assert "omitted" in str(msgs[1]["content"] or "")


def test_audit_degrades_embedded_image_payload() -> None:
    msgs = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "x"},
                {"type": "input_image", "image_base64": "a" * 600, "mime": "image/png"},
            ],
        }
    ]
    ensure_no_tool_or_embedded_image_payload(path="unit.image", messages=msgs)
    c = msgs[0]["content"]
    assert isinstance(c, list)
    assert any(isinstance(x, dict) and str(x.get("type") or "") == "text" and "omitted" in str(x.get("text") or "") for x in c)


def test_audit_degrades_large_base64_like_plain_text() -> None:
    payload = "A" * 700
    msgs = [{"role": "user", "content": payload}]
    ensure_no_tool_or_embedded_image_payload(path="unit.b64_text", messages=msgs)
    assert "omitted" in str(msgs[0]["content"] or "")
