from __future__ import annotations

from runtime.chat.tool_runtime import _attachments_from_tool_result


def test_attachments_from_tool_result_preserves_deliverable_flag() -> None:
    result = {
        "ok": True,
        "attachment_id": "att-doc-1",
        "mime": "text/plain",
        "name": "out.txt",
        "bytes": 12,
        "deliverable": True,
    }
    out = _attachments_from_tool_result(result)
    assert len(out) == 1
    assert out[0]["type"] == "text_ref"
    assert out[0].get("deliverable") is True


def test_attachments_from_tool_result_preserves_non_image_ref_types() -> None:
    result = {
        "attachments": [
            {
                "type": "text_ref",
                "attachment_id": "att-text-1",
                "mime": "text/plain",
                "name": "a.txt",
                "bytes": 12,
            },
            {
                "attachment_id": "att-video-1",
                "mime": "video/mp4",
                "name": "a.mp4",
                "bytes": 1024,
            },
        ]
    }

    out = _attachments_from_tool_result(result)
    by_id = {str(x.get("attachment_id")): x for x in out}

    assert by_id["att-text-1"]["type"] == "text_ref"
    assert by_id["att-video-1"]["type"] == "video_ref"

