"""DashScope / Model Studio **text-to-video** and **image-to-video** (async: create task → poll).

Used by the **video** specialist (Admin Chat + orchestration) to bypass the generic LLM tool loop,
analogous to :mod:`svc.llm.image_legacy_client` for the image specialist.

**Text-to-video:** ``input`` only ``prompt`` (plus optional ``audio_url`` / ``negative_prompt`` for some models).
Use a **t2v** model id.

**Image-to-video (Wan 2.6 and earlier):** ``input.img_url`` — HTTPS or ``data:image/...;base64,...``.

**Image-to-video (Wan 2.7 general API):** ``input.media``, e.g.
``[{"type": "first_frame", "url": "<https or data url>"}]``.
Do **not** send ``img_url`` for that path (see Alibaba *image-to-video-general* API reference).

Override with ``AIA_VIDEO_I2V_INPUT_STYLE=media|img_url``; default is **auto** (``wan2.7`` in model id → ``media``, else ``img_url``).

HTTP contract (region of ``base_url`` must match the API key):

- ``POST {root}/api/v1/services/aigc/video-generation/video-synthesis`` with header
  ``X-DashScope-Async: enable``
- ``GET {root}/api/v1/tasks/{task_id}`` until ``output.task_status`` is terminal

References:
- https://www.alibabacloud.com/help/en/model-studio/text-to-video-api-reference/
- https://www.alibabacloud.com/help/en/model-studio/image-to-video-api-reference/
- https://www.alibabacloud.com/help/en/model-studio/image-to-video-general-api-reference/
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Callable, Literal

import httpx

from svc.files.attachment_assets import AttachmentAssetStore
from svc.llm.image_http_common import (
    compress_data_url_image,
    dashscope_multimodal_http_ok,
    download_http_url_bytes,
    is_data_url,
    join_url,
    post_with_retry,
)

VIDEO_SPECIALIST_DEFAULT_PROMPT_ZH = "请根据描述生成一段短视频，画面稳定、主体清晰。"

_DEFAULT_SYNTHESIS_PATH = "api/v1/services/aigc/video-generation/video-synthesis"


def _truthy_env(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def env_video_expert_api_key() -> str:
    return (os.getenv("AIA_VIDEO_EXPERT_API_KEY") or "").strip()


def env_video_expert_base_url() -> str:
    return (os.getenv("AIA_VIDEO_EXPERT_BASE_URL") or "").strip()


def env_video_expert_model() -> str:
    return (os.getenv("AIA_VIDEO_EXPERT_MODEL") or "").strip()


def _effective_video_model_for_request(model_name: str, *, img_url: str | None) -> str:
    """DashScope Wan: **text-to-video** ids use ``*-t2v-*``; **image-to-video** needs ``*-i2v-*``.

    Chat profiles often configure only a **t2v** model; if we still submit ``input.img_url``, the gateway
    may largely follow the prompt and ignore the photograph (looks like unrelated output). When a first
    frame is present we therefore coerce ``-t2v-`` → ``-i2v-`` unless disabled or overridden.
    """
    m = (model_name or "").strip()
    if not m:
        return m
    if not str(img_url or "").strip():
        return m
    if _truthy_env("AIA_VIDEO_EXPERT_DISABLE_I2V_MODEL_COERCION"):
        return m
    override = (os.getenv("AIA_VIDEO_EXPERT_I2V_MODEL") or "").strip()
    if override:
        return override
    if "-t2v-" in m:
        coerced = m.replace("-t2v-", "-i2v-", 1)
        if coerced != m:
            return coerced
    low = m.lower().rstrip()
    if low.endswith("-t2v"):
        coerced = m[: -len("-t2v")] + "-i2v"
        if coerced != m:
            return coerced
    return m


def _i2v_first_frame_input_style(*, model_name: str) -> Literal["img_url", "media"]:
    """How to pass the first-frame image: legacy ``img_url`` vs Wan 2.7 ``media`` array."""
    raw = (os.getenv("AIA_VIDEO_I2V_INPUT_STYLE") or "").strip().lower()
    if raw in ("media", "wan27", "general"):
        return "media"
    if raw in ("img_url", "legacy", "wan26"):
        return "img_url"
    ml = (model_name or "").strip().lower()
    return "media" if "wan2.7" in ml else "img_url"


def env_video_expert_synthesis_path() -> str:
    raw = (os.getenv("AIA_VIDEO_EXPERT_SYNTHESIS_PATH") or "").strip().lstrip("/")
    return raw or _DEFAULT_SYNTHESIS_PATH


def _poll_interval_sec() -> float:
    raw = (os.getenv("AIA_VIDEO_EXPERT_POLL_INTERVAL_SEC") or "").strip()
    if not raw:
        return 15.0
    try:
        return max(3.0, min(float(raw), 120.0))
    except ValueError:
        return 15.0


def _max_wait_sec() -> float:
    raw = (os.getenv("AIA_VIDEO_EXPERT_MAX_WAIT_SEC") or "").strip()
    if not raw:
        return 900.0
    try:
        return max(30.0, min(float(raw), 3600.0))
    except ValueError:
        return 900.0


def dashscope_api_root_from_base_url(base_url: str) -> str:
    """Strip OpenAI-compatible suffixes so native DashScope paths can be joined."""
    b = (base_url or "").strip().rstrip("/")
    if not b:
        return ""
    root = re.sub(r"/compatible-mode/v\d+(?:/.*)?$", "", b, flags=re.IGNORECASE).rstrip("/")
    if not root or root == b:
        root = re.sub(r"/compatible-mode/?$", "", b, flags=re.IGNORECASE).rstrip("/")
    return root or b


def _parameters_extra_from_env() -> dict[str, Any]:
    raw = (os.getenv("AIA_VIDEO_EXPERT_PARAMETERS_EXTRA") or "").strip()
    if not raw:
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _input_extra_from_env() -> dict[str, Any]:
    raw = (os.getenv("AIA_VIDEO_EXPERT_INPUT_EXTRA") or "").strip()
    if not raw:
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _dashscope_video_env_parameters() -> dict[str, Any]:
    out: dict[str, Any] = {}
    size = (os.getenv("DASHSCOPE_VIDEO_SIZE") or "").strip()
    if size:
        out["size"] = size
    raw_dur = (os.getenv("DASHSCOPE_VIDEO_DURATION") or "").strip()
    if raw_dur.isdigit():
        out["duration"] = max(1, min(int(raw_dur), 600))
    pe = (os.getenv("DASHSCOPE_VIDEO_PROMPT_EXTEND") or "").strip().lower()
    if pe in ("1", "true", "yes", "on"):
        out["prompt_extend"] = True
    elif pe in ("0", "false", "no", "off"):
        out["prompt_extend"] = False
    st = (os.getenv("DASHSCOPE_VIDEO_SHOT_TYPE") or "").strip()
    if st:
        out["shot_type"] = st
    wm = (os.getenv("DASHSCOPE_VIDEO_WATERMARK") or "").strip().lower()
    if wm in ("1", "true", "yes", "on"):
        out["watermark"] = True
    elif wm in ("0", "false", "no", "off"):
        out["watermark"] = False
    seed = (os.getenv("DASHSCOPE_VIDEO_SEED") or "").strip()
    if seed.isdigit():
        out["seed"] = max(0, min(int(seed), 2_147_483_647))
    return out


def _dashscope_video_env_input() -> dict[str, Any]:
    out: dict[str, Any] = {}
    neg = os.getenv("DASHSCOPE_VIDEO_NEGATIVE_PROMPT")
    if neg is not None and str(neg).strip():
        out["negative_prompt"] = str(neg)
    audio = (os.getenv("DASHSCOPE_VIDEO_AUDIO_URL") or "").strip()
    if audio:
        out["audio_url"] = audio
    return out


def _extract_output(body: dict[str, Any]) -> dict[str, Any]:
    out = body.get("output")
    return out if isinstance(out, dict) else {}


def _stderr_debug_video(url: str, payload: dict[str, Any]) -> None:
    if not _truthy_env("AIA_VIDEO_EXPERT_DEBUG_PRINT_PAYLOAD"):
        return
    try:
        txt = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        sys.stderr.write(f"\n[oclaw video_generation] POST {url}\n{txt}\n\n")
        sys.stderr.flush()
    except Exception:
        pass


def send_video_generation_request(
    *,
    prompt: str,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    img_url: str | None = None,
    timeout_submit_sec: float = 120.0,
    on_progress: Callable[[str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Create an async video task and poll until terminal state or timeout.

    When ``img_url`` is set (HTTPS URL or data URL), it becomes the first-frame reference: for Wan **2.7**
    i2v models this is sent as ``input.media`` with ``type: first_frame`` and ``url``; for older i2v models
    as ``input.img_url``.     Caller image overrides any overlapping keys from ``AIA_VIDEO_EXPERT_INPUT_EXTRA`` after merge
    (style selected by model id and ``AIA_VIDEO_I2V_INPUT_STYLE``).
    """
    resolved_key = (api_key or env_video_expert_api_key()).strip()
    raw_base = (base_url or env_video_expert_base_url()).strip()
    root = dashscope_api_root_from_base_url(raw_base)
    model_name = ((model or "").strip() or env_video_expert_model()).strip()
    if not resolved_key or not root:
        return {
            "ok": False,
            "error": "missing AIA_VIDEO_EXPERT_API_KEY or AIA_VIDEO_EXPERT_BASE_URL (or pass api_key and base_url)",
        }
    if not model_name:
        return {
            "ok": False,
            "error": "missing model (chosen profile/model=… or set AIA_VIDEO_EXPERT_MODEL)",
        }
    prompt_plain = str(prompt or "").strip()
    if not prompt_plain:
        prompt_plain = VIDEO_SPECIALIST_DEFAULT_PROMPT_ZH

    model_name = _effective_video_model_for_request(model_name, img_url=img_url)

    path = env_video_expert_synthesis_path()
    url_submit = join_url(root, path)
    input_body: dict[str, Any] = {
        **_input_extra_from_env(),
        **_dashscope_video_env_input(),
        "prompt": prompt_plain,
    }
    iu = str(img_url or "").strip()
    if iu:
        if is_data_url(iu):
            iu = compress_data_url_image(iu)
        _style = _i2v_first_frame_input_style(model_name=model_name)
        if _style == "media":
            input_body.pop("img_url", None)
            first = {"type": "first_frame", "url": iu}
            prev = input_body.get("media")
            rest: list[dict[str, Any]] = []
            if isinstance(prev, list):
                for item in prev:
                    if isinstance(item, dict) and str(item.get("type") or "").strip().lower() != "first_frame":
                        rest.append(dict(item))
            input_body["media"] = [first, *rest]
        else:
            input_body.pop("media", None)
            input_body["img_url"] = iu
    parameters: dict[str, Any] = {
        **_dashscope_video_env_parameters(),
        **_parameters_extra_from_env(),
    }
    payload = {"model": model_name, "input": input_body, "parameters": parameters}
    headers = {
        "Authorization": f"Bearer {resolved_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    _stderr_debug_video(url_submit, payload)

    submit_timeout = httpx.Timeout(max(30.0, float(timeout_submit_sec)), connect=45.0)
    with httpx.Client(timeout=submit_timeout, follow_redirects=True) as client:
        try:
            r = post_with_retry(client, url=url_submit, headers=headers, payload=payload)
        except Exception as e:
            return {"ok": False, "error": f"submit failed: {type(e).__name__}: {e}"}
        if r.status_code >= 400:
            return {"ok": False, "error": f"submit http {r.status_code}: {r.text[:800]}"}
        try:
            body = r.json()
        except Exception:
            return {"ok": False, "error": f"submit non-json: {r.text[:500]}"}
        if not isinstance(body, dict):
            return {"ok": False, "error": "submit response is not a JSON object"}
        ok0, err0 = dashscope_multimodal_http_ok(body)
        if not ok0:
            return {"ok": False, "error": err0 or "submit rejected by provider"}
        out0 = _extract_output(body)
        task_id = str(out0.get("task_id") or "").strip()
        st0 = str(out0.get("task_status") or "").strip().upper()
        v0 = str(out0.get("video_url") or "").strip()
        if st0 == "SUCCEEDED" and v0.startswith(("http://", "https://")):
            return {"ok": True, "video_urls": [v0], "task_id": task_id or None}
        if st0 in {"FAILED", "UNKNOWN"}:
            msg = str(out0.get("message") or out0.get("msg") or "").strip()
            code = str(out0.get("code") or "").strip()
            bit = f"{code}: {msg}".strip(": ").strip() or st0
            return {"ok": False, "error": bit, "task_id": task_id or None}
        if not task_id:
            return {"ok": False, "error": "submit response missing output.task_id", "raw": body}

    poll_interval = _poll_interval_sec()
    max_wait = _max_wait_sec()
    deadline = time.monotonic() + max_wait
    task_url = join_url(root, f"api/v1/tasks/{task_id}")
    headers_get = {"Authorization": f"Bearer {resolved_key}"}
    poll_timeout = httpx.Timeout(120.0, connect=45.0)
    with httpx.Client(timeout=poll_timeout, follow_redirects=True) as client:
        while time.monotonic() < deadline:
            if should_stop and should_stop():
                return {"ok": False, "error": "stopped", "task_id": task_id}
            try:
                gr = client.get(task_url, headers=headers_get)
            except Exception as e:
                return {"ok": False, "error": f"poll failed: {type(e).__name__}: {e}", "task_id": task_id}
            if gr.status_code >= 400:
                return {
                    "ok": False,
                    "error": f"poll http {gr.status_code}: {gr.text[:800]}",
                    "task_id": task_id,
                }
            try:
                tb = gr.json()
            except Exception:
                return {"ok": False, "error": f"poll non-json: {gr.text[:500]}", "task_id": task_id}
            if not isinstance(tb, dict):
                return {"ok": False, "error": "poll response not a JSON object", "task_id": task_id}
            okp, errp = dashscope_multimodal_http_ok(tb)
            if not okp:
                return {"ok": False, "error": errp or "poll rejected", "task_id": task_id}
            tout = _extract_output(tb)
            st = str(tout.get("task_status") or "").strip().upper()
            vurl = str(tout.get("video_url") or "").strip()
            if st == "SUCCEEDED" and vurl.startswith(("http://", "https://")):
                return {"ok": True, "video_urls": [vurl], "task_id": task_id}
            if st in {"FAILED", "UNKNOWN", "CANCELED"}:
                msg = str(tout.get("message") or tout.get("msg") or "").strip()
                code = str(tout.get("code") or "").strip()
                bit = f"{code}: {msg}".strip(": ").strip() or st
                return {"ok": False, "error": bit, "task_id": task_id}
            if on_progress and st in {"PENDING", "RUNNING"}:
                on_progress(f"oclaw: video task {st.lower()}…")
            time.sleep(poll_interval)

    return {"ok": False, "error": f"poll timeout after {int(max_wait)}s", "task_id": task_id}


def materialize_video_output_attachments(
    video_urls: Any,
    *,
    max_videos: int = 1,
) -> list[dict[str, Any]]:
    """Download remote MP4 (etc.) into ``video_ref`` rows; on failure fall back to best-effort metadata."""
    cap = max(1, min(int(max_videos), 4))
    produced: list[dict[str, Any]] = []
    if not isinstance(video_urls, list):
        return produced
    urls = [str(u).strip() for u in video_urls if str(u).strip().startswith(("http://", "https://"))]

    store = AttachmentAssetStore()
    ua = "Mozilla/5.0 (compatible; oclaw-video-expert/1.0; +https://github.com/)"
    for idx, u in enumerate(urls[:cap], start=1):
        try:
            blob, ctype = download_http_url_bytes(u, user_agent=ua)
            if not blob:
                raise ValueError("empty body")
            mime = (ctype.split(";", 1)[0].strip() if ctype else "") or "video/mp4"
            ext = ".mp4"
            if mime == "video/webm":
                ext = ".webm"
            elif mime in ("video/quicktime", "video/mov"):
                ext = ".mov"
            meta = store.save_bytes(blob, filename=f"video-output-{idx}{ext}", mime=mime)
            produced.append(
                {
                    "type": "video_ref",
                    "attachment_id": meta.attachment_id,
                    "name": meta.name,
                    "mime": meta.mime,
                    "bytes": meta.bytes,
                }
            )
        except Exception:
            produced.append(
                {
                    "type": "video_ref",
                    "name": f"video-output-{idx}.mp4",
                    "mime": "video/mp4",
                    "url": u,
                }
            )
    return produced


def legacy_video_turn_bundle(resp: dict[str, Any]) -> tuple[bool, str, list[dict[str, Any]]]:
    ok = bool(resp.get("ok"))
    text = str(resp.get("text") or "").strip()
    if not ok:
        err = str(resp.get("error") or "").strip()
        return False, f"Video generation failed: {err or 'unknown error'}", []
    urls = resp.get("video_urls")
    if not isinstance(urls, list):
        urls = []
    atts = materialize_video_output_attachments(urls, max_videos=1)
    if atts:
        return True, text, atts
    if text:
        return True, text, []
    return False, "Video specialist failed: empty response from provider.", []


def legacy_video_assistant_body_with_placeholder(
    *,
    lang: str | None,
    body_text: str,
    produced: list[dict[str, Any]] | None,
) -> str:
    if str(body_text or "").strip():
        return str(body_text or "")
    if produced:
        return (
            "Generated video (see attachment below)."
            if str(lang or "").startswith("en")
            else "已生成视频（见下方附件）。"
        )
    return str(body_text or "")


__all__ = [
    "VIDEO_SPECIALIST_DEFAULT_PROMPT_ZH",
    "dashscope_api_root_from_base_url",
    "env_video_expert_api_key",
    "env_video_expert_base_url",
    "env_video_expert_model",
    "legacy_video_assistant_body_with_placeholder",
    "legacy_video_turn_bundle",
    "materialize_video_output_attachments",
    "send_video_generation_request",
]
