from __future__ import annotations

import base64
import json

import pytest

from runtime.tools.public.cloudflare_image_generate_tool import _to_image_bytes


def test_to_image_bytes_accepts_direct_image_content_type() -> None:
    raw = b"fake-image-bytes"
    out, mime = _to_image_bytes(raw, "image/png; charset=binary")
    assert out == raw
    assert mime == "image/png"


def test_to_image_bytes_accepts_data_url_in_result() -> None:
    payload = base64.b64encode(b"png-bytes").decode("ascii")
    resp = {
        "success": True,
        "result": {"image": f"data:image/png;base64,{payload}"},
    }
    out, mime = _to_image_bytes(json.dumps(resp).encode("utf-8"), "application/json")
    assert out == b"png-bytes"
    assert mime == "image/png"


def test_to_image_bytes_accepts_plain_base64_result() -> None:
    payload = base64.b64encode(b"jpg-bytes").decode("ascii")
    resp = {
        "success": True,
        "result": {"b64_json": payload},
    }
    out, mime = _to_image_bytes(json.dumps(resp).encode("utf-8"), "application/json")
    assert out == b"jpg-bytes"
    assert mime == "image/png"


def test_to_image_bytes_raises_on_error_response() -> None:
    resp = {"success": False, "errors": [{"message": "bad request"}]}
    with pytest.raises(ValueError, match="success"):
        _to_image_bytes(json.dumps(resp).encode("utf-8"), "application/json")
