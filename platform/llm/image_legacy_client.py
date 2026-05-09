"""Legacy image+text payloads for DashScope-style gateways.

Uses ``{"image":...}/{"text":...}`` or typed compatible-mode blocks on ``/chat/completions`` only.
Prefer :mod:`oclaw.platform.llm.image_ocr_client` for OpenAI-compatible vision (图片专家已改用该路径).
"""

from __future__ import annotations

from typing import Any

import httpx

from oclaw.platform.llm.image_http_common import (
    compress_data_url_image,
    env_ocr_lane_api_key,
    env_ocr_lane_base_url,
    env_ocr_lane_model,
    env_ocr_lane_chat_endpoint,
    extract_text_and_images,
    is_data_url,
    join_url,
    post_with_retry,
)
from oclaw.runtime.prompt_templates import render_prompt


def _http_content_blocks(images: list[str], prompt: str, *, typed: bool) -> list[dict[str, Any]]:
    prompt_text = str(prompt or "").strip() or render_prompt("image/default_edit_prompt.zh.md", strict=True)
    if not typed:
        blocks: list[dict[str, Any]] = [{"image": img} for img in images]
        blocks.append({"text": prompt_text})
        return blocks
    blocks_typed: list[dict[str, Any]] = [{"type": "image", "image": img} for img in images]
    blocks_typed.append({"type": "text", "text": prompt_text})
    return blocks_typed


def send_legacy_image_messages(
    *,
    images: list[str],
    prompt: str,
    model: str | None = None,
    timeout_sec: int = 60,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Legacy multimodal HTTP (non--OpenAI-``image_url`` schema). Optional; specialists use OCR client."""
    resolved_base_url = (base_url or env_ocr_lane_base_url()).strip()
    resolved_api_key = (api_key or env_ocr_lane_api_key()).strip()
    model_name = ((model or "").strip() or env_ocr_lane_model())
    endpoint = env_ocr_lane_chat_endpoint()
    url = join_url(resolved_base_url, endpoint)
    if not resolved_api_key or not resolved_base_url:
        return {
            "ok": False,
            "error": "missing AIA_OCR_API_KEY or AIA_OCR_BASE_URL (or pass api_key and base_url)",
        }
    if not model_name:
        return {
            "ok": False,
            "error": "missing AIA_OCR_MODEL (or pass model=...) — no default model id",
        }
    if not images:
        return {"ok": False, "error": "at least one image input is required"}

    raw_selected = [str(x).strip() for x in images if str(x).strip()][:3]
    selected: list[str] = []
    input_kind: list[str] = []
    for img in raw_selected:
        if is_data_url(img):
            selected.append(compress_data_url_image(img))
            input_kind.append("data_url")
            continue
        if img.startswith("http://") or img.startswith("https://"):
            selected.append(img)
            input_kind.append("url")
            continue
    if not selected:
        return {"ok": False, "error": "no usable image input (expected URL or data URL)"}

    prefer_typed_http = "compatible-mode" in resolved_base_url.lower()
    content_multi = _http_content_blocks(selected, prompt, typed=prefer_typed_http)
    content_multi_fallback = _http_content_blocks(selected, prompt, typed=not prefer_typed_http)

    headers = {
        "Authorization": f"Bearer {resolved_api_key}",
        "Content-Type": "application/json",
    }
    payload_multi = {
        "model": model_name,
        "messages": [{"role": "user", "content": content_multi}],
    }
    payload_single = {
        "model": model_name,
        "messages": [{"role": "user", "content": content_multi_fallback[-2:] if len(content_multi_fallback) >= 2 else content_multi_fallback}],
    }

    with httpx.Client(timeout=float(timeout_sec)) as client:
        try:
            r = post_with_retry(client, url=url, headers=headers, payload=payload_multi)
        except Exception as e:
            return {"ok": False, "error": f"http request failed: {type(e).__name__}: {e}", "backend_shape": "multi"}

        if r.status_code >= 400:
            try:
                r2 = post_with_retry(client, url=url, headers=headers, payload=payload_single)
            except Exception as e:
                return {
                    "ok": False,
                    "error": f"http fallback request failed: {type(e).__name__}: {e}",
                    "backend_shape": "single-fallback-failed",
                }
            if r2.status_code >= 400:
                return {
                    "ok": False,
                    "error": f"http {r2.status_code}: {r2.text[:500]}",
                    "backend_shape": "single-fallback-failed",
                }
            try:
                obj2 = r2.json()
            except Exception:
                return {"ok": False, "error": f"non-json response: {r2.text[:500]}", "backend_shape": "single"}
            text, out_images = extract_text_and_images(obj2 if isinstance(obj2, dict) else {})
            return {
                "ok": True,
                "text": text,
                "images": out_images,
                "backend_shape": "single",
                "input_kind": input_kind[-1:] if input_kind else ["data_url"],
            }

        try:
            obj = r.json()
        except Exception:
            return {"ok": False, "error": f"non-json response: {r.text[:500]}", "backend_shape": "multi"}
        text, out_images = extract_text_and_images(obj if isinstance(obj, dict) else {})
        return {
            "ok": True,
            "text": text,
            "images": out_images,
            "backend_shape": "multi",
            "input_kind": input_kind if input_kind else ["data_url"],
        }


__all__ = ["send_legacy_image_messages"]
