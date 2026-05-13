from __future__ import annotations

import runtime.tools.public.query_video_attachment_tool as vq


def test_normalized_video_meta_extracts_top_level_fields() -> None:
    obj = {
        "format": {"duration": "12.50"},
        "streams": [
            {"codec_type": "audio", "sample_rate": "48000"},
            {"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": "30000/1001"},
        ],
    }
    out = vq._normalized_video_meta(obj)
    assert float(out.get("duration_sec") or 0.0) > 12.0
    assert int(out.get("width") or 0) == 1920
    assert int(out.get("height") or 0) == 1080
    assert float(out.get("fps") or 0.0) > 29.0

