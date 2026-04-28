from __future__ import annotations

import base64

from oclaw.runtime.chat.media_redact import ingest_embedded_image_blobs_as_refs, redact_embedded_image_blobs


def test_redact_nested_mcp_image_block() -> None:
    big = "/9j/" + "a" * 800
    obj = {
        "ok": True,
        "result": {"content": [{"type": "image", "mime": "image/jpeg", "data": big}]},
    }
    out = redact_embedded_image_blobs(obj)
    assert out["result"]["content"][0].get("_image_payload_redacted") is True
    assert "data" not in out["result"]["content"][0]
    assert isinstance(out["result"]["content"][0].get("_redacted_payload_chars"), int)


def test_redact_keeps_small_data_field() -> None:
    obj = {"type": "image", "mime": "image/png", "data": "abc"}
    assert redact_embedded_image_blobs(obj) == obj


def test_ingest_embedded_image_blob_as_ref(tmp_path) -> None:
    raw = base64.b64encode(b"png-bytes").decode("ascii")
    obj = {"result": {"content": [{"type": "image", "mime": "image/png", "data": raw, "name": "x.png"}]}}
    out, refs = ingest_embedded_image_blobs_as_refs(obj, root_dir=str(tmp_path), filename_prefix="unit")
    block = out["result"]["content"][0]
    assert block["type"] == "image_ref"
    assert str(block.get("attachment_id") or "")
    assert "data" not in block
    assert refs and refs[0]["attachment_id"] == block["attachment_id"]


def test_ingest_embedded_binary_blob_as_binary_ref(tmp_path) -> None:
    raw = base64.b64encode(b"%PDF-1.4-fake").decode("ascii")
    obj = {"result": {"content": [{"type": "file", "mime": "application/pdf", "base64": raw, "name": "a.pdf"}]}}
    out, refs = ingest_embedded_image_blobs_as_refs(obj, root_dir=str(tmp_path), filename_prefix="unit")
    block = out["result"]["content"][0]
    assert block["type"] == "binary_ref"
    assert str(block.get("attachment_id") or "")
    assert "base64" not in block
    assert refs and refs[0]["attachment_id"] == block["attachment_id"]
