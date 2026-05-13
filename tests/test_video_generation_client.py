from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from svc.llm.video_generation_client import (
    _effective_video_model_for_request,
    _i2v_first_frame_input_style,
    dashscope_api_root_from_base_url,
    legacy_video_assistant_body_with_placeholder,
    legacy_video_turn_bundle,
    materialize_video_output_attachments,
    send_video_generation_request,
)


def test_dashscope_api_root_strips_compatible_suffix() -> None:
    assert (
        dashscope_api_root_from_base_url("https://dashscope.aliyuncs.com/compatible-mode/v1")
        == "https://dashscope.aliyuncs.com"
    )


def test_send_video_generation_missing_config() -> None:
    r = send_video_generation_request(prompt="hello", api_key="", base_url="", model="wan2.2-t2v-plus")
    assert r["ok"] is False
    assert "missing" in str(r.get("error") or "").lower()


def test_send_video_generation_poll_succeeds() -> None:
    post_resp = MagicMock()
    post_resp.status_code = 200
    post_resp.json.return_value = {"output": {"task_id": "tid-1", "task_status": "PENDING"}}

    get_pending = MagicMock()
    get_pending.status_code = 200
    get_pending.json.return_value = {"output": {"task_id": "tid-1", "task_status": "PENDING"}}

    get_ok = MagicMock()
    get_ok.status_code = 200
    get_ok.json.return_value = {
        "output": {
            "task_id": "tid-1",
            "task_status": "SUCCEEDED",
            "video_url": "https://example.invalid/out.mp4",
        }
    }

    clients: list[MagicMock] = []

    def _client_factory(*_a, **_k):
        inst = MagicMock()
        inst.__enter__ = lambda *_x: inst
        inst.__exit__ = lambda *_x: None
        if len(clients) == 1:
            inst.get.side_effect = [get_pending, get_ok]
        clients.append(inst)
        return inst

    with patch("svc.llm.video_generation_client.httpx.Client", side_effect=_client_factory):
        with patch(
            "svc.llm.video_generation_client.post_with_retry",
            return_value=post_resp,
        ):
            with patch("svc.llm.video_generation_client.time.sleep"):
                r = send_video_generation_request(
                    prompt="cat",
                    model="wan2.2-t2v-plus",
                    api_key="sk-test",
                    base_url="https://dashscope.aliyuncs.com",
                )

    assert r["ok"] is True
    assert r.get("video_urls") == ["https://example.invalid/out.mp4"]
    assert len(clients) == 2
    assert clients[1].get.call_count == 2


def test_legacy_video_turn_bundle_ok_without_materialize() -> None:
    ok, text, att = legacy_video_turn_bundle(
        {"ok": True, "text": "done", "video_urls": ["https://example.invalid/x.mp4"]}
    )
    assert ok is True
    assert text == "done"
    assert len(att) >= 1
    assert att[0].get("type") == "video_ref"


def test_legacy_video_placeholder_zh() -> None:
    produced = [{"type": "video_ref", "attachment_id": "a" * 64}]
    s = legacy_video_assistant_body_with_placeholder(lang="zh", body_text="", produced=produced)
    assert "视频" in s


def test_materialize_video_output_attachments_empty() -> None:
    assert materialize_video_output_attachments([], max_videos=1) == []


def test_effective_video_model_coerces_t2v_to_i2v_when_image() -> None:
    assert _effective_video_model_for_request("wan2.6-t2v-flash", img_url="https://x/a.png") == "wan2.6-i2v-flash"
    assert _effective_video_model_for_request("wan2.6-i2v-flash", img_url="https://x/a.png") == "wan2.6-i2v-flash"
    assert _effective_video_model_for_request("wan2.6-t2v-flash", img_url=None) == "wan2.6-t2v-flash"
    assert _effective_video_model_for_request("wan2.6-t2v-flash", img_url="") == "wan2.6-t2v-flash"
    assert _effective_video_model_for_request("wan2.7-t2v", img_url="https://x/a.png") == "wan2.7-i2v"


def test_i2v_input_style_auto(monkeypatch) -> None:
    monkeypatch.delenv("AIA_VIDEO_I2V_INPUT_STYLE", raising=False)
    assert _i2v_first_frame_input_style(model_name="wan2.7-i2v") == "media"
    assert _i2v_first_frame_input_style(model_name="WAN2.7-i2v-plus") == "media"
    assert _i2v_first_frame_input_style(model_name="wan2.6-i2v-flash") == "img_url"


def test_send_video_coerces_payload_model_when_t2v_plus_img(monkeypatch) -> None:
    monkeypatch.delenv("AIA_VIDEO_EXPERT_I2V_MODEL", raising=False)
    monkeypatch.delenv("AIA_VIDEO_EXPERT_DISABLE_I2V_MODEL_COERCION", raising=False)
    post_resp = MagicMock()
    post_resp.status_code = 200
    post_resp.json.return_value = {
        "output": {
            "task_id": "tid-i2v",
            "task_status": "SUCCEEDED",
            "video_url": "https://example.invalid/i2v.mp4",
        }
    }
    inst = MagicMock()
    inst.__enter__ = lambda *_x: inst
    inst.__exit__ = lambda *_x: None
    captured: dict[str, Any] = {}

    def _capture_post(_client, **kw):
        p = kw.get("payload")
        if isinstance(p, dict):
            captured.clear()
            captured.update(p)
        return post_resp

    with patch("svc.llm.video_generation_client.httpx.Client", return_value=inst):
        with patch("svc.llm.video_generation_client.post_with_retry", side_effect=_capture_post):
            r = send_video_generation_request(
                prompt="motion",
                model="wan2.6-t2v-flash",
                api_key="k",
                base_url="https://dashscope.aliyuncs.com",
                img_url="https://example.invalid/frame.png",
            )
    assert r["ok"] is True
    assert captured.get("model") == "wan2.6-i2v-flash"


def test_send_video_includes_img_url_in_payload() -> None:
    post_resp = MagicMock()
    post_resp.status_code = 200
    post_resp.json.return_value = {
        "output": {
            "task_id": "tid-i2v",
            "task_status": "SUCCEEDED",
            "video_url": "https://example.invalid/i2v.mp4",
        }
    }
    inst = MagicMock()
    inst.__enter__ = lambda *_x: inst
    inst.__exit__ = lambda *_x: None
    captured: dict[str, Any] = {}

    def _capture_post(_client, **kw):
        p = kw.get("payload")
        if isinstance(p, dict):
            captured.clear()
            captured.update(p)
        return post_resp

    with patch("svc.llm.video_generation_client.httpx.Client", return_value=inst):
        with patch("svc.llm.video_generation_client.post_with_retry", side_effect=_capture_post):
            r = send_video_generation_request(
                prompt="motion",
                model="wan2.6-i2v-flash",
                api_key="k",
                base_url="https://dashscope.aliyuncs.com",
                img_url="https://example.invalid/frame.png",
            )
    assert r["ok"] is True
    inp = captured.get("input")
    assert isinstance(inp, dict)
    assert inp.get("img_url") == "https://example.invalid/frame.png"
    assert inp.get("media") is None


def test_send_video_wan27_uses_media_first_frame(monkeypatch) -> None:
    monkeypatch.delenv("AIA_VIDEO_I2V_INPUT_STYLE", raising=False)
    post_resp = MagicMock()
    post_resp.status_code = 200
    post_resp.json.return_value = {
        "output": {
            "task_id": "tid-i2v",
            "task_status": "SUCCEEDED",
            "video_url": "https://example.invalid/i2v.mp4",
        }
    }
    inst = MagicMock()
    inst.__enter__ = lambda *_x: inst
    inst.__exit__ = lambda *_x: None
    captured: dict[str, Any] = {}

    def _capture_post(_client, **kw):
        p = kw.get("payload")
        if isinstance(p, dict):
            captured.clear()
            captured.update(p)
        return post_resp

    u = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250925/wpimhv/rap.png"
    with patch("svc.llm.video_generation_client.httpx.Client", return_value=inst):
        with patch("svc.llm.video_generation_client.post_with_retry", side_effect=_capture_post):
            r = send_video_generation_request(
                prompt="你好",
                model="wan2.7-i2v",
                api_key="k",
                base_url="https://dashscope.aliyuncs.com",
                img_url=u,
            )
    assert r["ok"] is True
    inp = captured.get("input")
    assert isinstance(inp, dict)
    assert inp.get("img_url") is None
    media = inp.get("media")
    assert isinstance(media, list) and len(media) >= 1
    assert media[0].get("type") == "first_frame"
    assert media[0].get("url") == u


def test_send_immediate_succeeded_on_submit() -> None:
    post_resp = MagicMock()
    post_resp.status_code = 200
    post_resp.json.return_value = {
        "output": {
            "task_id": "tid-x",
            "task_status": "SUCCEEDED",
            "video_url": "https://example.invalid/immediate.mp4",
        }
    }
    inst = MagicMock()
    inst.__enter__ = lambda *_x: inst
    inst.__exit__ = lambda *_x: None
    with patch("svc.llm.video_generation_client.httpx.Client", return_value=inst):
        with patch(
            "svc.llm.video_generation_client.post_with_retry",
            return_value=post_resp,
        ):
            r = send_video_generation_request(
                prompt="x",
                model="m",
                api_key="k",
                base_url="https://dashscope.aliyuncs.com",
            )
    assert r["ok"] is True
    assert r["video_urls"] == ["https://example.invalid/immediate.mp4"]
