"""Shared HTTP helpers for OCR and legacy image lanes (internal)."""

from __future__ import annotations

import base64
import io
import os
import time
from typing import Any

import httpx
from PIL import Image


def join_url(base: str, path: str) -> str:
    b = (base or "").rstrip("/")
    p = (path or "").lstrip("/")
    return f"{b}/{p}"


def env_ocr_lane_api_key() -> str:
    return (os.getenv("AIA_OCR_API_KEY") or "").strip()


def env_ocr_lane_base_url() -> str:
    return (os.getenv("AIA_OCR_BASE_URL") or "").strip()


def env_ocr_lane_model() -> str:
    return (os.getenv("AIA_OCR_MODEL") or "").strip()


def env_ocr_lane_chat_endpoint() -> str:
    raw = (os.getenv("AIA_OCR_CHAT_ENDPOINT") or "").strip()
    return raw or "/chat/completions"


def is_data_url(s: str) -> bool:
    return s.startswith("data:") and ";base64," in s


def compress_data_url_image(
    data_url: str,
    *,
    max_side: int = 1600,
    max_bytes: int = 2 * 1024 * 1024,
    jpeg_quality: int = 82,
) -> str:
    if not is_data_url(data_url):
        return data_url
    try:
        header, b64 = data_url.split(";base64,", 1)
        mime = header.replace("data:", "", 1).strip() or "image/jpeg"
        raw = base64.b64decode(b64.encode("ascii"))
        if len(raw) <= max_bytes:
            return data_url

        with Image.open(io.BytesIO(raw)) as im:
            im = im.convert("RGB")
            w, h = im.size
            longest = max(w, h)
            if longest > max_side:
                scale = max_side / float(longest)
                nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)

            out = io.BytesIO()
            im.save(out, format="JPEG", quality=max(30, min(95, int(jpeg_quality))), optimize=True)
            blob = out.getvalue()
            if not blob:
                return data_url
            b64_new = base64.b64encode(blob).decode("ascii")
            return f"data:{'image/jpeg' if mime.startswith('image/') else mime};base64,{b64_new}"
    except Exception:
        return data_url


def post_with_retry(
    client: httpx.Client,
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    retries: int = 3,
    backoff_sec: float = 0.8,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            return client.post(url, headers=headers, json=payload)
        except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt >= retries:
                break
            time.sleep(backoff_sec * (2 ** (attempt - 1)))
    assert last_exc is not None
    raise last_exc


def extract_text_and_images(resp_json: dict[str, Any]) -> tuple[str, list[str]]:
    text_parts: list[str] = []
    images: list[str] = []
    choices = resp_json.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(msg, dict):
            c = msg.get("content")
            if isinstance(c, str):
                text_parts.append(c)
            elif isinstance(c, list):
                for it in c:
                    if not isinstance(it, dict):
                        continue
                    if isinstance(it.get("text"), str):
                        text_parts.append(str(it.get("text")))
                    elif isinstance(it.get("image"), str):
                        images.append(str(it.get("image")))
                    elif isinstance(it.get("image_url"), str):
                        images.append(str(it.get("image_url")))
                    elif isinstance(it.get("image_url"), dict) and isinstance(it["image_url"].get("url"), str):
                        images.append(str(it["image_url"]["url"]))
                    elif isinstance(it.get("b64_json"), str):
                        images.append(f"data:image/png;base64,{it['b64_json']}")

    if not images:
        data = resp_json.get("data")
        if isinstance(data, list):
            for it in data:
                if not isinstance(it, dict):
                    continue
                if isinstance(it.get("url"), str):
                    images.append(str(it.get("url")))
                if isinstance(it.get("b64_json"), str):
                    images.append(f"data:image/png;base64,{it['b64_json']}")
    return "\n".join([x for x in text_parts if x]).strip(), images


__all__ = [
    "compress_data_url_image",
    "env_ocr_lane_api_key",
    "env_ocr_lane_base_url",
    "env_ocr_lane_chat_endpoint",
    "env_ocr_lane_model",
    "extract_text_and_images",
    "is_data_url",
    "join_url",
    "post_with_retry",
]
