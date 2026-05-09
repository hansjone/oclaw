"""OCR / vision lane: OpenAI-compatible multimodal ``image_url`` + ``text`` only."""

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

# Shared with query_image_attachment and OpenAI-compat multimodal→text downgrade.
VISION_OCR_EXTRACT_PROMPT_ZH = (
    "请只提取图片中可见文字并按阅读顺序输出。"
    "如果有表格，保持行列结构；不确定的内容标注为[unclear]。"
)
VISION_DESCRIBE_PROMPT_ZH = (
    "请详细描述这张图片的主要内容、对象、场景和可见文字。"
    "回答请使用要点列表，避免臆测。"
)


def _http_content_blocks_openai_vision(images: list[str], prompt: str) -> list[dict[str, Any]]:
    prompt_text = str(prompt or "").strip() or render_prompt("image/default_edit_prompt.zh.md", strict=True)
    blocks: list[dict[str, Any]] = []
    for img in images:
        s = str(img or "").strip()
        if not s:
            continue
        blocks.append({"type": "image_url", "image_url": {"url": s}})
    if prompt_text:
        blocks.append({"type": "text", "text": prompt_text})
    return blocks


def vision_llm_backend_status(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    ak = (api_key or env_ocr_lane_api_key()).strip()
    bu = (base_url or env_ocr_lane_base_url()).strip()
    md = ((model or "").strip() or env_ocr_lane_model())
    if ak and bu and md:
        return {"ok": True, "backend": "aia_ocr_http"}
    return {
        "ok": False,
        "backend": None,
        "hint_zh": (
            "未配置 OCR/看图通道：请同时设置 AIA_OCR_BASE_URL、AIA_OCR_API_KEY、AIA_OCR_MODEL"
            "（OpenAI-compatible 多模态 /chat/completions）。不设默认模型 id。"
        ),
        "hint_en": (
            "OCR/vision lane not configured: set AIA_OCR_BASE_URL, AIA_OCR_API_KEY, and AIA_OCR_MODEL. "
            "No default model id."
        ),
    }


def send_ocr_image_messages(
    *,
    images: list[str],
    prompt: str,
    model: str | None = None,
    timeout_sec: int = 60,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """OpenAI Chat Completions multimodal only (``/chat/completions``): multi-image then single-image."""
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

    content_openai = _http_content_blocks_openai_vision(selected, prompt)
    content_openai_single = _http_content_blocks_openai_vision(selected[-1:], prompt) if selected else []

    headers = {
        "Authorization": f"Bearer {resolved_api_key}",
        "Content-Type": "application/json",
    }
    payload_openai_multi = {
        "model": model_name,
        "messages": [{"role": "user", "content": content_openai}],
    }
    payload_openai_single = {
        "model": model_name,
        "messages": [{"role": "user", "content": content_openai_single}],
    }

    def _ok_response(resp: httpx.Response) -> tuple[dict[str, Any] | None, bool]:
        if resp.status_code >= 400:
            return None, False
        try:
            obj = resp.json()
        except Exception:
            return None, False
        if not isinstance(obj, dict):
            return None, False
        text, out_imgs = extract_text_and_images(obj)
        if not str(text or "").strip():
            return obj, False
        return {"text": text, "images": out_imgs}, True

    err_last = ""
    with httpx.Client(timeout=float(timeout_sec)) as client:
        try:
            r0 = post_with_retry(client, url=url, headers=headers, payload=payload_openai_multi)
        except Exception as e:
            return {"ok": False, "error": f"http request failed: {type(e).__name__}: {e}", "backend_shape": "openai-multi"}
        if r0 is not None:
            if r0.status_code >= 400:
                err_last = f"http {r0.status_code}: {r0.text[:500]}"
            else:
                parsed, ok = _ok_response(r0)
                if ok and isinstance(parsed, dict):
                    return {
                        "ok": True,
                        "text": str(parsed.get("text") or ""),
                        "images": list(parsed.get("images") or []),
                        "backend_shape": "openai-multi",
                        "input_kind": input_kind if input_kind else ["data_url"],
                    }

        try:
            r1 = post_with_retry(client, url=url, headers=headers, payload=payload_openai_single)
        except Exception as e:
            return {
                "ok": False,
                "error": err_last or f"openai-single request failed: {type(e).__name__}: {e}",
                "backend_shape": "openai-single-failed",
            }
        if r1.status_code >= 400:
            return {
                "ok": False,
                "error": err_last or f"http {r1.status_code}: {r1.text[:500]}",
                "backend_shape": "openai-single-failed",
            }
        try:
            obj1 = r1.json()
        except Exception:
            return {"ok": False, "error": f"non-json response: {r1.text[:500]}", "backend_shape": "openai-single"}
        text, out_images = extract_text_and_images(obj1 if isinstance(obj1, dict) else {})
        out: dict[str, Any] = {
            "ok": bool(str(text or "").strip()),
            "text": text,
            "images": out_images,
            "backend_shape": "openai-single",
            "input_kind": input_kind[-1:] if input_kind else ["data_url"],
        }
        if not str(text or "").strip():
            out["error"] = "empty assistant text after openai-single"
        return out


__all__ = [
    "VISION_DESCRIBE_PROMPT_ZH",
    "VISION_OCR_EXTRACT_PROMPT_ZH",
    "send_ocr_image_messages",
    "vision_llm_backend_status",
]
